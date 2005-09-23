# -*- coding: iso-8859-1 -*-
"""
    MoinMoin - Despam action
    
    Mass revert changes done by some specific author / bot.

    @copyright: 2005 by ???, Thomas Waldmann
    @license: GNU GPL, see COPYING for details.
"""

import time, urllib

from MoinMoin.logfile import editlog
from MoinMoin.util.dataset import TupleDataset, Column
from MoinMoin.widget.browser import DataBrowserWidget
from MoinMoin import wikiutil, Page, PageEditor
from MoinMoin.macro import RecentChanges
from MoinMoin.formatter.text_html import Formatter

def show_editors(request, pagename, timestamp):
    _ =  request.getText
    
    timestamp = int(timestamp * 1000000)
    log = editlog.EditLog(request)
    editors = {}
    pages = {}
    for line in log.reverse():
        if line.ed_time_usecs < timestamp:
            break
        
        if not request.user.may.read(line.pagename):
            continue
        
        editor = line.getEditor(request)
        if not pages.has_key(line.pagename):
            pages[line.pagename] = 1
            editors[editor] = editors.get(editor, 0) + 1
            
    editors = [(nr, editor) for editor, nr in editors.iteritems()]
    editors.sort()

    pg = Page.Page(request, pagename)

    dataset = TupleDataset()
    dataset.columns = [Column('editor', label=_("Editor"), align='left'),
                       Column('pages', label=_("Pages"), align='right'),
                       Column('link', label='', align='left')]
    for nr, editor in editors:
        dataset.addRow((editor, unicode(nr), pg.link_to(request, text=_("Select Author"), querystr="action=Despam&editor=%s" % urllib.quote_plus(editor))))
    
    table = DataBrowserWidget(request)
    table.setData(dataset)
    table.render()

class tmp:
    pass

def show_pages(request, pagename, editor, timestamp):
    _ =  request.getText
    
    timestamp = int(timestamp * 1000000)
    log = editlog.EditLog(request)
    lines = []
    pages = {}
    #  mimic macro object for use of RecentChanges subfunctions
    macro = tmp()
    macro.request = request
    macro.formatter = Formatter(request)

    request.write("<p>")
    for line in log.reverse():
        if line.ed_time_usecs < timestamp:
            break
        
        if not request.user.may.read(line.pagename):
            continue
        
        
        if not pages.has_key(line.pagename):
            pages[line.pagename] = 1
            if line.getEditor(request) == editor:
                request.write(RecentChanges.format_page_edits(macro, [line], timestamp))

    request.write('''
</p>
<p>
<form method="post" action="%s/%s">
<input type="hidden" name="action" value="Despam">
<input type="hidden" name="editor" value="%s">
<input type="submit" name="ok" value="%s">
</form>
</p>
''' % (request.getScriptname(), wikiutil.quoteWikinameURL(pagename),
       urllib.quote(editor), _("Revert all!")))

def revert_page(request, pagename, editor):
    if not request.user.may.revert(pagename):
        return 

    log = editlog.EditLog(request, rootpagename=pagename)

    first = True
    rev = u"00000000"
    for line in log.reverse():
        if first:
            first = False
            if line.getEditor(request) != editor:
                return
        else:
            if line.getEditor(request) != editor:
                rev = line.rev
                break
    oldpg = Page.Page(request, pagename, rev=int(rev))
    pg = PageEditor.PageEditor(request, pagename)
    try:
        savemsg = pg.saveText(oldpg.get_raw_body(), 0, extra=rev, action="SAVE/REVERT")
    except pg.SaveError, msg:
        # msg contain a unicode string
        savemsg = unicode(msg)
    return savemsg
    
def revert_pages(request, editor, timestamp):
    _ =  request.getText

    editor = urllib.unquote(editor)
    timestamp = int(timestamp * 1000000)
    log = editlog.EditLog(request)
    pages = {}
    messages = []
    for line in log.reverse():
        if line.ed_time_usecs < timestamp:
            break

        if not request.user.may.read(line.pagename):
            continue

        if not pages.has_key(line.pagename):
            pages[line.pagename] = 1
            if line.getEditor(request) == editor:
                msg = revert_page(request, line.pagename, editor)
                if msg:
                    request.write("<p>%s: %s</p>" % (
                        Page.Page(request, line.pagename).link_to(request), msg))

def execute(pagename, request):
    _ = request.getText
    # be extra paranoid in dangerous actions
    actname = __name__.split('.')[-1]
    if actname in request.cfg.actions_excluded or \
       request.user.name not in request.cfg.superuser:
        return Page.Page(request, pagename).send_page(request,
            msg = _('You are not allowed to use this action.'))

    editor = request.form.get('editor', [None])[0]
    timestamp = time.time() - 24 * 3600
       # request.form.get('timestamp', [None])[0]
    ok = request.form.get('ok', [0])[0]

    wikiutil.send_title(request, "Despam", pagename=pagename)    
    # Start content (important for RTL support)
    request.write(request.formatter.startContent("content"))
    
    if ok:
        revert_pages(request, editor, timestamp)
    elif editor:
        show_pages(request, pagename, editor, timestamp)
    else:
        show_editors(request, pagename, timestamp)

    # End content and send footer
    request.write(request.formatter.endContent())
    wikiutil.send_footer(request, pagename, editable=0, showactions=0, form=request.form)

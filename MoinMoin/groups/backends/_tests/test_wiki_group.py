# -*- coding: iso-8859-1 -*-
"""
    MoinMoin - MoinMoin.groups.backends.wiki_group tests

    @copyright: 2003-2004 by Juergen Hermann <jh@web.de>,
                2007 by MoinMoin:ThomasWaldmann
                2008 by MoinMoin:MelitaMihaljevic
                2009 by MoinMoin:DmitrijsMilajevs
    @license: GNU GPL, see COPYING for details.

"""

from py.test import raises
import re, shutil

from MoinMoin.groups.backends import wiki_group
from MoinMoin import Page, security
from MoinMoin.PageEditor import PageEditor
from MoinMoin.user import User
from MoinMoin._tests import append_page, become_trusted, create_page, create_random_string_list, nuke_page, nuke_user, wikiconfig
from MoinMoin.groups import GroupManager

class TestWikiGroupPage:
    """
    Test what backend extracts from a group page and what is ignored.
    """

    class Config(wikiconfig.Config):
        def group_manager_init(self, request):
            return GroupManager(backends=[wiki_group.Backend(request)])

    def test_CamelCase(self):
        text = """
 * CamelCase
"""
        assert u'CamelCase' in self.get_group(text)

    def test_extended_name(self):
        text = """
 * extended name
"""
        assert u'extended name' in self.get_group(text)

    def test_extended_link(self):
        text = """
 * [[extended link]]
"""
        assert u'extended link' in self.get_group(text)

    def test_ignore_second_level_list(self):
        text = """
  * second level
   * third level
    * forth level
     * and then some...
"""
        assert len([x for x in self.get_group(text)]) == 0

    def test_ignore_other(self):
        text = """
= ignore this =
 * take this

Ignore previous line and this text.
"""
        assert u'take this' in self.get_group(text)

    def test_strip_whitespace(self):
        text = """
 *   take this
"""
        assert u'take this' in self.get_group(text)

    def get_group(self, text):
        request = self.request
        become_trusted(request)
        create_page(request, u'SomeTestGroup', text)
        group = request.groups[u'SomeTestGroup']
        nuke_page(request, u'SomeTestGroup')
        return group


class TestWikiGroupBackend:

    class Config(wikiconfig.Config):
        def group_manager_init(self, request):
            return GroupManager(backends=[wiki_group.Backend(request)])

    def setup_class(self):
        become_trusted(self.request)

        test_groups = {u'EditorGroup': [u'AdminGroup', u'John', u'JoeDoe', u'Editor'],
                            u'AdminGroup': [u'Admin', u'Admin2', u'John'],
                            u'OtherGroup': [u'SomethingOther']}

        self.expanded_groups = {u'EditorGroup': [u'Admin', u'Admin2', u'John',
                                                 u'JoeDoe', u'Editor'],
                                u'AdminGroup': [u'Admin', u'Admin2', u'John'],
                                u'OtherGroup': [u'SomethingOther']}

        for (group, members) in test_groups.iteritems():
            page_text = ' * %s' % '\n * '.join(members)
            create_page(self.request, group, page_text)

    def teardown_class(self):
        become_trusted(self.request)

        for group in self.expanded_groups:
            nuke_page(self.request, group)
        
    def test_contains(self):
        """
        Test group_wiki Backend and Group containment methods.
        """
        groups = self.request.groups

        for (group, members) in self.expanded_groups.iteritems():
            print group
            assert group in groups
            for member in members:
                assert member in groups[group]

        raises(KeyError, lambda: groups[u'NotExistingGroup'])

    def test_iter(self):
        groups = self.request.groups

        for (group, members) in self.expanded_groups.iteritems():
            returned_members = [x for x in groups[group]]
            assert len(returned_members) == len(members)
            for member in members:
                assert member in returned_members

    def test_membergroups(self):
        groups = self.request.groups

        john_groups = groups.membergroups(u'John')
        assert 2 == len(john_groups)
        assert u'EditorGroup' in john_groups
        assert u'AdminGroup' in john_groups
        assert u'ThirdGroup' not in john_groups

    def test_rename_group_page(self):
        """
        Tests if the groups cache is refreshed after renaming a Group page.
        """
        request = self.request
        become_trusted(request)

        page = create_page(request, u'SomeGroup', u" * ExampleUser")
        page.renamePage('AnotherGroup')

        result = u'ExampleUser' in request.groups[u'AnotherGroup']
        nuke_page(request, u'AnotherGroup')

        assert result is True

    def test_copy_group_page(self):
        """
        Tests if the groups cache is refreshed after copying a Group page.
        """
        request = self.request
        become_trusted(request)

        page = create_page(request, u'SomeGroup', u" * ExampleUser")
        page.copyPage(u'SomeOtherGroup')

        result = u'ExampleUser' in request.groups[u'SomeOtherGroup']

        nuke_page(request, u'OtherGroup')
        nuke_page(request, u'SomeGroup')

        assert result is True

    def test_appending_group_page(self):
        """
        Test scalability by appending a name to a large list of group members.
        """
        request = self.request
        become_trusted(request)

        # long list of users
        page_content = [u" * %s" % member for member in create_random_string_list(length=15, count=30000)]
        test_user = create_random_string_list(length=15, count=1)[0]
        create_page(request, u'UserGroup', "\n".join(page_content))
        append_page(request, u'UserGroup', u' * %s' % test_user)
        result = test_user in request.groups['UserGroup']
        nuke_page(request, u'UserGroup')

        assert result

    def test_user_addition_to_group_page(self):
        """
        Test addition of a username to a large list of group members.
        """
        request = self.request
        become_trusted(request)

        # long list of users
        page_content = [u" * %s" % member for member in create_random_string_list()]
        create_page(request, u'UserGroup', "\n".join(page_content))

        new_user = create_random_string_list(length=15, count=1)[0]
        append_page(request, u'UserGroup', u' * %s' % new_user)
        user = User(request, name=new_user)
        if not user.exists():
            User(request, name=new_user, password=new_user).save()

        result = new_user in request.groups[u'UserGroup']
        nuke_page(request, u'UserGroup')
        nuke_user(request, new_user)

        assert result

    def test_member_removed_from_group_page(self):
        """
        Tests appending a member to a large list of group members and
        recreating the page without the member.
        """
        request = self.request
        become_trusted(request)

        # long list of users
        page_content = [u" * %s" % member for member in create_random_string_list()]
        page_content = "\n".join(page_content)
        create_page(request, u'UserGroup', page_content)

        test_user = create_random_string_list(length=15, count=1)[0]
        page = append_page(request, u'UserGroup', u' * %s' % test_user)

        # saves the text without test_user
        page.saveText(page_content, 0)
        result = test_user in request.groups[u'UserGroup']
        nuke_page(request, u'UserGroup')

        assert not result

    def test_group_page_user_addition_trivial_change(self):
        """
        Test addition of a user to a group page by trivial change.
        """
        request = self.request
        become_trusted(request)

        test_user = create_random_string_list(length=15, count=1)[0]
        member = u" * %s\n" % test_user
        page = create_page(request, u'UserGroup', member)

        # next member saved  as trivial change
        test_user = create_random_string_list(length=15, count=1)[0]
        member = u" * %s\n" % test_user
        page.saveText(member, 0, trivial=1)

        result = test_user in request.groups[u'UserGroup']

        nuke_page(request, u'UserGroup')

        assert result

    def test_wiki_backend_acl_allow(self):
        """
        Test if the wiki group backend works with acl code.
        Check user which has rights.
        """
        request = self.request
        become_trusted(request)

        create_page(request, u'FirstGroup', u" * OtherUser")

        acl_rights = ["FirstGroup:admin,read,write"]
        acl = security.AccessControlList(request.cfg, acl_rights)

        allow = acl.may(request, u"OtherUser", "admin")

        nuke_page(request, u'FirstGroup')

        assert allow, 'OtherUser has read rights because he is member of FirstGroup'

    def test_wiki_backend_acl_deny(self):
        """
        Test if the wiki group backend works with acl code.
        Check user which does not have rights.
        """
        request = self.request
        become_trusted(request)

        create_page(request, u'FirstGroup', u" * OtherUser")

        acl_rights = ["FirstGroup:read,write"]
        acl = security.AccessControlList(request.cfg, acl_rights)

        other_user_allow = acl.may(request, u"OtherUser", "admin")
        some_user_allow = acl.may(request, u"SomeUser", "read")

        nuke_page(request, u'FirstGroup')

        assert not other_user_allow, 'OtherUser does not have admin rights because it is not listed in acl'
        assert not some_user_allow, 'SomeUser does not have admin read right because he is not listed in the FirstGroup'

    def test_wiki_backend_page_acl_append_page(self):
        """
        Test if the wiki group backend works with acl code.
        First check acl rights of a user that is not a member of group
        then add user member to a page group and check acl rights
        """
        request = self.request
        become_trusted(request)

        create_page(request, u'NewGroup', u" * ExampleUser")

        acl_rights = ["NewGroup:read,write"]
        acl = security.AccessControlList(request.cfg, acl_rights)

        has_rights_before = acl.may(request, u"AnotherUser", "read")

        # update page - add AnotherUser to a page group NewGroup
        append_page(request, u'NewGroup', u" * AnotherUser")

        has_rights_after = acl.may(request, u"AnotherUser", "read")

        nuke_page(request, u'NewGroup')

        assert not has_rights_before, 'AnotherUser has no read rights because in the beginning he is not a member of a group page NewGroup'
        assert has_rights_after, 'AnotherUser must have read rights because after appendage he is member of NewGroup'


    def test_wiki_backend_page_acl_with_all(self):
        request = self.request
        become_trusted(request)

        acl_rights = ["EditorGroup:read,write,delete,admin All:read"]
        acl = security.AccessControlList(request.cfg, acl_rights)


        for member in self.expanded_groups[u'EditorGroup']:
            assert acl.may(request, member, "read")
            assert acl.may(request, member, "write")
            assert acl.may(request, member, "delete")
            assert acl.may(request, member, "admin")

        assert acl.may(request, u"Someone", "read")
        assert not acl.may(request, u"Someone", "write")
        assert not acl.may(request, u"Someone", "delete")
        assert not acl.may(request, u"Someone", "admin")


coverage_modules = ['MoinMoin.groups.backends.wiki_group']


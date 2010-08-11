# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Sync Server
#
# The Initial Developer of the Original Code is the Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Tarek Ziade (tarek@mozilla.com)
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****
"""
Redis + SQL backend
"""
import json
from time import time

import redis
from weaveserver.storage.sql import WeaveSQLStorage

_SQLURI = 'mysql://sync:sync@localhost/sync'


def _key(*args):
    return ':'.join([str(arg) for arg in args])


class RediSQLStorage(WeaveSQLStorage):
    """Uses Redis when possible/useful, SQL otherwise.
    """

    def __init__(self, sqluri=_SQLURI, standard_collections=False,
                 redis_host='localhost', redis_port=6379):
        super(RediSQLStorage, self).__init__(sqluri, standard_collections)
        self._conn = redis.Redis(host=redis_host, port=redis_port)
        self._conn.ping()  # will generate a connection error if down

    @classmethod
    def get_name(self):
        return 'redisql'

    def _is_meta_global(self, collection_name, item_id):
        return collection_name == 'meta' and item_id == 'global'

    def item_exists(self, user_id, collection_name, item_id):
        """Returns a timestamp if an item exists."""
        if self._is_meta_global(collection_name, item_id):
            value = self._conn.get(_key('meta', 'global', user_id))
            if value is not None:
                wbo = json.loads(value)
                return wbo['modified']

        return super(RediSQLStorage, self).item_exists(user_id,
                                                       collection_name,
                                                       item_id)

    def get_item(self, user_id, collection_name, item_id, fields=None):
        """Returns one item.

        If the item is meta/global, we want to get the cached one if present.
        """
        if self._is_meta_global(collection_name, item_id):
            value = self._conn.get(_key('meta', 'global', user_id))
            if value is not None:
                return json.loads(value)

        return super(RediSQLStorage, self).get_item(user_id, collection_name,
                                                    item_id, fields)

    def set_item(self, user_id, collection_name, item_id, **values):
        """Adds or update an item"""
        values['collection'] = self._get_collection_id(user_id,
                                                       collection_name)
        values['id'] = item_id
        values['username'] = user_id
        if 'payload' in values and 'modified' not in values:
            values['modified'] = time()

        if self._is_meta_global(collection_name, item_id):
            self._conn.set(_key('meta', 'global', user_id),
                           json.dumps(values))

        return self._set_item(user_id, collection_name, item_id, **values)

    def set_items(self, user_id, collection_name, items):
        """Adds or update a batch of items.

        Returns a list of success or failures.
        """
        if self._is_meta_global(collection_name, items[0]['id']):
            values = items[0]
            values['username'] = user_id
            self._conn.set(_key('meta', 'global', user_id),
                           json.dumps(values))
        return super(RediSQLStorage, self).set_items(user_id, collection_name,
                                                     items)

    def delete_item(self, user_id, collection_name, item_id):
        """Deletes an item"""
        if self._is_meta_global(collection_name, item_id):
            self._conn.set(_key('meta', 'global', user_id), None)

        return super(RediSQLStorage, self).delete_item(user_id,
                                                       collection_name,
                                                       item_id)

    def delete_items(self, user_id, collection_name, item_ids=None,
                     filters=None, limit=None, offset=None, sort=None):
        """Deletes items. All items are removed unless item_ids is provided"""
        if (collection_name == 'meta' and (item_ids is None
            or 'global' in item_ids)):
            self._conn.set(_key('meta', 'global', user_id), None)

        return super(RediSQLStorage, self).delete_items(user_id,
                                                        collection_name,
                                                        item_ids, filters,
                                                        limit, offset, sort)

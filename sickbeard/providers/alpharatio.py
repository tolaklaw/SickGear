# coding=utf-8
#
# Author: SickGear
#
# This file is part of SickGear.
#
# SickGear is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickGear is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickGear.  If not, see <http://www.gnu.org/licenses/>.

import re
import traceback

from . import generic
from sickbeard import logger, tvcache
from sickbeard.bs4_parser import BS4Parser
from sickbeard.helpers import tryInt
from lib.unidecode import unidecode


class AlphaRatioProvider(generic.TorrentProvider):

    def __init__(self):

        generic.TorrentProvider.__init__(self, 'AlphaRatio')

        self.url_base = 'https://alpharatio.cc/'
        self.urls = {'config_provider_home_uri': self.url_base,
                     'login': self.url_base + 'login.php',
                     'search': self.url_base + 'torrents.php?searchstr=%s%s&' + '&'.join(
                         ['tags_type=1', 'order_by=time', 'order_way=desc'] +
                         ['filter_cat[%s]=1' % c for c in 1, 2, 3, 4, 5] +
                         ['action=basic', 'searchsubmit=1']),
                     'get': self.url_base + '%s'}

        self.url = self.urls['config_provider_home_uri']

        self.username, self.password, self.minseed, self.minleech = 4 * [None]
        self.freeleech = False
        self.cache = AlphaRatioCache(self)

    def _authorised(self, **kwargs):

        return super(AlphaRatioProvider, self)._authorised(logged_in=(lambda x=None: self.has_all_cookies('session')),
                                                           post_params={'keeplogged': '1', 'login': 'Login'})

    def _search_provider(self, search_params, **kwargs):

        results = []
        if not self._authorised():
            return results

        items = {'Cache': [], 'Season': [], 'Episode': [], 'Propers': []}

        rc = dict((k, re.compile('(?i)' + v)) for (k, v) in {'info': 'view', 'get': 'download'}.items())
        for mode in search_params.keys():
            for search_string in search_params[mode]:
                search_string = isinstance(search_string, unicode) and unidecode(search_string) or search_string
                search_url = self.urls['search'] % (search_string, ('', '&freetorrent=1')[self.freeleech])

                html = self.get_url(search_url)

                cnt = len(items[mode])
                try:
                    if not html or self._has_no_results(html):
                        raise generic.HaltParseException

                    with BS4Parser(html, features=['html5lib', 'permissive']) as soup:
                        torrent_table = soup.find('table', attrs={'id': 'torrent_table'})
                        torrent_rows = [] if not torrent_table else torrent_table.find_all('tr')

                        if 2 > len(torrent_rows):
                            raise generic.HaltParseException

                        for tr in torrent_rows[1:]:
                            try:
                                seeders, leechers, size = [tryInt(n, n) for n in [
                                    tr.find_all('td')[x].get_text().strip() for x in (-2, -1, -4)]]
                                if self._peers_fail(mode, seeders, leechers):
                                    continue

                                title = tr.find('a', title=rc['info']).get_text().strip()

                                link = str(tr.find('a', title=rc['get'])['href']).replace('&amp;', '&').lstrip('/')
                                download_url = self.urls['get'] % link
                            except (AttributeError, TypeError, ValueError):
                                continue

                            if title and download_url:
                                items[mode].append((title, download_url, seeders, self._bytesizer(size)))

                except generic.HaltParseException:
                    pass
                except Exception:
                    logger.log(u'Failed to parse. Traceback: %s' % traceback.format_exc(), logger.ERROR)
                self._log_search(mode, len(items[mode]) - cnt, search_url)

            self._sort_seeders(mode, items)

            results = list(set(results + items[mode]))

        return results


class AlphaRatioCache(tvcache.TVCache):

    def __init__(self, this_provider):
        tvcache.TVCache.__init__(self, this_provider)

        self.update_freq = 20  # cache update frequency

    def _cache_data(self):

        return self.provider.cache_data()


provider = AlphaRatioProvider()

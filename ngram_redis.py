"""
:mod:`ngram` -- Provides a set that supports lookup by string similarity
========================================================================

.. moduleauthor:: Graham Poulter (version 3.0+)
.. moduleauthor:: Michel Albert (version 2.0.0b2)
"""

from __future__ import division

__license__ = """
This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 2.1 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

See LICENSE file or http://www.gnu.org/licenses/lgpl-2.1.html
"""

import redis

from ngram_abstract import NGramAbstract

class NGramRedis(NGramAbstract):
    """A set that supports lookup by NGram string similarity.

    Accepts `unicode` string or an encoded `str` of bytes. With encoded `str` the
    splitting is on byte boundaries, which will be incorrect if the encoding uses
    multiple bytes per character.  You must provide NGram with unicode strings if
    the encoding would have multi-byte characters.

    :type threshold: float in 0.0 ... 1.0

    :param threshold: minimum similarity for a string to be considered a match.

    :type warp: float in 1.0 ... 3.0

    :param warp: use warp greater than 1.0 to increase the similarity of shorter string pairs.

    :type items: [item, ...]

    :param items: iteration of items to index for N-gram search.

    :type N: int >= 2

    :param N: number of characters per n-gram.

    :type pad_len: int in 0 ... N-1

    :param pad_len: how many characters padding to add (defaults to N-1).

    :type pad_char: str or unicode

    :param pad_char: character to use for padding.  Default is '$', but consider using the\
    non-breaking space character, ``u'\\xa0'`` (``u"\\u00A0"``).

    :type key: function(item) -> str/unicode

    :param key: Function to convert items into string, default is no conversion.

    :param db: redis database to use

    :param enable_auto_blacklist: allow to automatically blacklist the ngrams\
    present in more than 10% of the items

    Instance variables:

    :ivar _grams: For each n-gram, the items containing it and the number of times\
    the n-gram occurs in the item as ``{str:{item:int, ...}, ...}``.

    :ivar length: maps items to length of the padded string representations as
    ``{item:int, ...}``.
    """

    def __init__(self, items=[], threshold=0.0, warp=1.0, key=None,
                    N=3, pad_len=None, pad_char='$', db=0,
                    enable_auto_blacklist=True):
        super(NGramRedis, self).__init__(items, threshold , warp, key, N,
                pad_len, pad_char)
        self.r = redis.Redis(db=db)
        self.enable_auto_blacklist = enable_auto_blacklist
        self.blacklist = []

    def add(self, item, item_id):
        """Add an item to the N-gram index (only if it has not already been added).

        >>> n = NGram()
        >>> n.add("ham")
        >>> n
        NGram(['ham'])
        >>> n.add("spam")
        >>> n
        NGram(['ham', 'spam'])
        """
        # Record length of padded string
        if item is None:
            return
        padded_item = self.pad(self.key(item))
        p = self.r.pipeline()
        for ngram in self._split(padded_item):
            p.zcard(ngram)
        zcards = p.execute()
        pipeline = self.r.pipeline(False)
        pipeline.hset("item_length", item_id, len(padded_item))
        i = -1
        for ngram in self._split(padded_item):
            if self.enable_auto_blacklist:
                i += 1
                if ngram in self.blacklist:
                    continue
                # Item present in > 10% of the items
                if item_id > 100000 and zcards[i] > (int(item_id) / 10):
                    pipeline.delete(ngram)
                    self.blacklist.append(ngram)
                    continue
            # Add a new n-gram and string to index if necessary
            # Increment number of times the n-gram appears in the string
            pipeline.zincrby(ngram, item_id)
        pipeline.execute()


    def items_sharing_ngrams(self, query):
        """Retrieve the subset of items that share n-grams the query string.

        :param query: look up items that share N-grams with this string.
        :return: dictionary from matched string to the number of shared N-grams.

        >>> n = NGram(["ham","spam","eggs"])
        >>> n.items_sharing_ngrams("mam")
        {'ham': 2, 'spam': 2}
        """
        # From matched string to number of N-grams shared with query string
        query = query.lower()
        shared = {}
        for ngram in self.split(query):
            for match, count in self.r.zrange(ngram, 0, -1, withscores=True):
                if shared.get(match) is None:
                    shared[match] = 1
                else:
                    shared[match] += 1
                # try with it:
                #shared[match] += count
        return shared


    def get_item_length(self, match):
        return int(self.r.hget("item_length", match))

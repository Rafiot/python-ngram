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

from ngram_abstract import NGramAbstract

class NGram(set, NGramAbstract):
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

    Instance variables:

    :ivar _grams: For each n-gram, the items containing it and the number of times\
    the n-gram occurs in the item as ``{str:{item:int, ...}, ...}``.

    :ivar length: maps items to length of the padded string representations as
    ``{item:int, ...}``.
    """

    def __init__(self, items=[], threshold=0.0, warp=1.0, key=None,
                    N=3, pad_len=None, pad_char='$'):
        set.__init__(self)
        self.length = {}
        NGramAbstract.__init__(self, items, threshold , warp, key, N, pad_len,
                pad_char)

    def __reduce__(self):
        """Return state information for pickling, no references to this instance.
        The key function must be None, a builtin function, or a named
        module-level function.

        >>> n = NGram([0xDEADBEEF, 0xBEEF], key=hex)
        >>> import pickle
        >>> p = pickle.dumps(n)
        >>> m = pickle.loads(p)
        >>> m
        NGram([3735928559, 48879])
        """
        return NGram, (list(self), self.threshold, self.warp, self._key,
                       self.N, self._pad_len, self._pad_char)

    def copy(self):
        """Return a shallow copy of the NGram object.  That is, instantiate
        a new NGram from references to items stored in this one.

        >>> from copy import deepcopy
        >>> n = NGram(['eggs', 'spam'])
        >>> m = n.copy()
        >>> m.add('ham')
        >>> n
        NGram(['eggs', 'spam'])
        >>> m
        NGram(['eggs', 'ham', 'spam'])
        """
        return NGram(self, self.threshold, self.warp, self._key,
                     self.N, self._pad_len, self._pad_char)

    def add(self, item):
        """Add an item to the N-gram index (only if it has not already been added).

        >>> n = NGram()
        >>> n.add("ham")
        >>> n
        NGram(['ham'])
        >>> n.add("spam")
        >>> n
        NGram(['ham', 'spam'])
        """
        if item not in self:
            # Add the item to the base set
            super(NGram, self).add(item)
            # Record length of padded string
            padded_item = self.pad(self.key(item))
            self.length[item] = len(padded_item)
            for ngram in self._split(padded_item):
                # Add a new n-gram and string to index if necessary
                self._grams.setdefault(ngram, {}).setdefault(item, 0)
                # Increment number of times the n-gram appears in the string
                self._grams[ngram][item] += 1

    def remove(self, item):
        """Remove an item from the index. Inverts the add operation.

        >>> n = NGram(['spam', 'eggs'])
        >>> n.remove('spam')
        >>> n
        NGram(['eggs'])
        """
        if item in self:
            super(NGram, self).remove(item)
            del self.length[item]
            for ngram in self.splititem(item):
                del self._grams[ngram][item]

    def items_sharing_ngrams(self, query):
        """Retrieve the subset of items that share n-grams the query string.

        :param query: look up items that share N-grams with this string.
        :return: dictionary from matched string to the number of shared N-grams.

        >>> n = NGram(["ham","spam","eggs"])
        >>> n.items_sharing_ngrams("mam")
        {'ham': 2, 'spam': 2}
        """
        # From matched string to number of N-grams shared with query string
        shared = {}
        # Dictionary mapping n-gram to string to number of occurrences of that
        # ngram in the string that remain to be matched.
        remaining = {}
        for ngram in self.split(query):
            try:
                for match, count in self._grams[ngram].iteritems():
                    remaining.setdefault(ngram, {}).setdefault(match, count)
                    # match up to as many occurrences of ngram as exist in the matched string
                    if remaining[ngram][match] > 0:
                        remaining[ngram][match] -= 1
                        shared.setdefault(match, 0)
                        shared[match] += 1
            except KeyError:
                pass
        return shared

    def get_item_length(self, match):
        return self.length[match]

    @staticmethod
    def compare(s1, s2, **kwargs):
        """Compares two strings and returns their similarity.

        :param s1: first string
        :param s2: second string
        :param kwargs: additional keyword arguments passed to __init__.
        :return: similarity between 0.0 and 1.0.

        >>> from ngram import NGram
        >>> NGram.compare('spa', 'spam')
        0.375
        >>> NGram.compare('ham', 'bam')
        0.25
        >>> NGram.compare('spam', 'pam') #N=2
        0.375
        >>> NGram.compare('ham', 'ams', N=1)
        0.5
        """
        if s1 is None or s2 is None:
            if s1 == s2:
                return 1.0
            return 0.0
        try:
            return NGram([s1], **kwargs).search(s2)[0][1]
        except IndexError:
            return 0.0

    def difference_update(self, other):
        """Remove from this set all elements from `other` set.

        >>> n = NGram(['spam', 'eggs'])
        >>> other = set(['spam'])
        >>> n.difference_update(other)
        >>> n
        NGram(['eggs'])
        """
        for x in other:
            self.discard(x)

    def intersection_update(self, other):
        """Update the set with the intersection of itself and `other`.

        >>> n = NGram(['spam', 'eggs'])
        >>> other = set(['spam', 'ham'])
        >>> n.intersection_update(other)
        >>> n
        NGram(['spam'])
        """
        self.difference_update([x for x in self if x not in other])

    def symmetric_difference_update(self, other):
        """Update the set with the symmetric difference of itself and `other`.

        >>> n = NGram(['spam', 'eggs'])
        >>> other = set(['spam', 'ham'])
        >>> n.intersection_update(other)
        >>> n
        NGram(['spam'])
        """
        intersection = self.intersection(other) # record intersection of sets
        self.update(other) # add items present in other
        self.difference_update(self, intersection) # remove items present in both


    def update(self, items):
        """Update the set with new items.

        >>> n = NGram(["spam"])
        >>> n.update(["eggs"])
        >>> n
        NGram(['eggs', 'spam'])
        """
        for item in items:
            self.add(item)

    def discard(self, item):
        """If `item` is a member of the set, remove it.

        >>> n = NGram(['spam', 'eggs'])
        >>> n.discard('spam')
        >>> n.discard('ham')
        >>> n
        NGram(['eggs'])
        """
        if item in self:
            self.remove(item)

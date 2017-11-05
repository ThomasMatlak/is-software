import music21 as m21
from collections import defaultdict


class MarkovChain(object):
    """  """

    def __init__(self, order=1):
        """  """
        self.order = order
        self.transition_matrix = self.generate_nested_defaultdict(self.order + 1)

    def generate_nested_defaultdict(self, depth):
        """ Create a nested collections.defaultdict object with depth `depth` """
        if depth == 1:
            return defaultdict(int)
        else:
            return defaultdict(lambda: self.generate_nested_defaultdict(depth - 1))

    def arbitrary_depth_get(self, subscripts, default=None, d=None):
        """ Access nested dict elements at arbitrary depths

            https://stackoverflow.com/questions/28225552/is-there-a-recursive-version-of-pythons-dict-get-built-in
        """
        if d is None:
            d = self.transition_matrix

        if not subscripts:
            return d
        key = subscripts[0]
        if isinstance(d, int):
            return d
        return self.arbitrary_depth_get(subscripts[1:], default=default, d=d.get(key, default))

    def arbitrary_depth_set(self, subscripts, _dict={}, val=None):
        """ Set nested dict elements at arbitrary depths

            https://stackoverflow.com/questions/33663332/python-adding-updating-dict-element-of-any-depth
        """

        if not subscripts:
            return _dict
        for sub in subscripts[:-1]:
            if '_x' not in locals():
                if sub not in _dict:
                    _dict[sub] = {}
                _x = _dict.get(sub)
            else:
                if sub not in _x:
                    _x[sub] = {}
                _x = _x.get(sub)
        _x[subscripts[-1]] = val
        return _dict

    def create_transition_matrix(self, streams, chain_type):
        """  """
        for stream in streams:
            prev_notes = []

            for n in range(len(stream)):
                note = stream[n]

                if len(prev_notes) < (self.order + 1):
                    prev_notes.append(note)
                    continue
                else:
                    if chain_type == "interval" or chain_type == "i":
                        intervals = []
                        for i in range(self.order):
                            intervals.append(m21.interval.Interval(prev_notes[i], prev_notes[i + 1]))

                        intervals.append(m21.interval.Interval(prev_notes[-1], note))

                        self.transition_matrix = self.arbitrary_depth_set(
                            [interval.directedName for interval in intervals[0:self.order + 1]],
                            self.transition_matrix,
                            self.arbitrary_depth_get([interval.directedName for interval in intervals[0:self.order + 1]], default=0) + 1
                        )
                    elif chain_type == "rhythm" or chain_type == "r":
                        self.transition_matrix = self.arbitrary_depth_set(
                            [prev_note.quarterLength for prev_note in prev_notes],
                            self.transition_matrix,
                            self.arbitrary_depth_get([prev_note.quarterLength for prev_note in prev_notes], default=0) + 1
                        )

                    for i in range(self.order):
                        prev_notes[i] = prev_notes[i + 1]

                    prev_notes[self.order] = note

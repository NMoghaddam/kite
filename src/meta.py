#!/bin/python


def property_cached(func):
    var_name = '_cached_' + func.__name__

    def cache_return(instance, *args, **kwargs):
        cache_return.__doc__ = func.__doc__
        if instance.__dict__.get(var_name, None) is None:
            instance.__dict__[var_name] = func(instance)
        return instance.__dict__[var_name]

    def cache_return_setter(instance, value):
        instance.__dict__[var_name] = value

    return property(fget=cache_return,
                    fset=cache_return_setter,
                    doc=func.__doc__)


class Subject(object):
    '''Subject - Obsever model realization '''
    def __init__(self):
        self._listeners = list()

    def subscribe(self, listener):
        self._listeners.append(listener)

    def unsubscribe(self, listener):
        self._listeners.remove(listener)

    def _notify(self, msg=''):
        for l in self._listeners:
            l()

__all__ = '''
Subject
'''.split()

# -*- coding: utf-8 -*-
# ELEKTRONN2 Toolkit
# Copyright (c) 2015 Marius Killinger
# All rights reserved

"""
Provides completions for the Python language, file sytem paths and a custom list of words
    for the ELEKTRONN2/Elektronn prompt_toolkit shell.

This module is mostly based on
- https://github.com/jonathanslenders/ptpython/blob/master/ptpython/completer.py
- https://github.com/jonathanslenders/ptpython/blob/master/ptpython/utils.py
(at git revision 32827385cca65eabefccb06b56e4cf9d2c1e0120),
which both are available under the following license (thanks, Jonathan and contributors!):

    Copyright (c) 2015, Jonathan Slenders
    All rights reserved.

    Redistribution and use in source and binary forms, with or without modification,
    are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice, this
      list of conditions and the following disclaimer.

    * Redistributions in binary form must reproduce the above copyright notice, this
      list of conditions and the following disclaimer in the documentation and/or
      other materials provided with the distribution.

    * Neither the name of the {organization} nor the names of its
      contributors may be used to endorse or promote products derived from
      this software without specific prior written permission.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
    ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
    WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
    DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
    ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
    (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
    LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
    ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
    (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
    SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

from __future__ import unicode_literals, absolute_import, division, \
    print_function

import jedi
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.contrib.completers import PathCompleter
from prompt_toolkit.contrib.regular_languages.compiler import \
    compile as compile_grammar
from prompt_toolkit.contrib.regular_languages.completion import \
    GrammarCompleter

import re


# From https://github.com/jonathanslenders/ptpython/blob/master/ptpython/utils.py
def _get_jedi_script_from_document(document, locals, globals):
    try:
        return jedi.Interpreter(document.text,
                                column=document.cursor_position_col,
                                line=document.cursor_position_row + 1,
                                path='input-text',
                                namespaces=[locals, globals])
    except ValueError:
        # Invalid cursor position.
        # ValueError('`column` parameter is not in a valid range.')
        return None
    except AttributeError:
        # Workaround for #65: https://github.com/jonathanslenders/python-prompt-toolkit/issues/65
        # See also: https://github.com/davidhalter/jedi/issues/508
        return None
    except IndexError:
        # Workaround Jedi issue #514: for https://github.com/davidhalter/jedi/issues/514
        return None
    except KeyError:
        # Workaroud for a crash when the input is "u'", the start of a unicode string.
        return None


# Based on https://github.com/jonathanslenders/ptpython/blob/master/ptpython/completer.py,
#     with additional word completions through the words argument
class NumaCompleter(Completer):
    """
    Completer for Python, file system paths and custom words
    """

    def __init__(self, get_globals, get_locals, words=None,
                 words_metastring=''):
        super(NumaCompleter, self).__init__()

        if words is None:
            words = []

        self.get_globals = get_globals
        self.get_locals = get_locals
        self.words = words

        # Appears next to all word completions to distinguish them from the Python language completions
        self.words_metastring = words_metastring

        self._path_completer_cache = None
        self._path_completer_grammar_cache = None

    @property
    def _path_completer(self):
        if self._path_completer_cache is None:
            self._path_completer_cache = GrammarCompleter(
                self._path_completer_grammar,
                {'var1': PathCompleter(expanduser=True),
                 'var2': PathCompleter(expanduser=True),})
        return self._path_completer_cache

    @property
    def _path_completer_grammar(self):
        """
        Return the grammar for matching paths inside strings inside Python
        code.
        """
        # We make this lazy, because it delays startup time a little bit.
        # This way, the grammar is build during the first completion.
        if self._path_completer_grammar_cache is None:
            self._path_completer_grammar_cache = self._create_path_completer_grammar()
        return self._path_completer_grammar_cache

    def _create_path_completer_grammar(self):
        def unwrapper(text):
            return re.sub(r'\\(.)', r'\1', text)

        def single_quoted_wrapper(text):
            return text.replace('\\', '\\\\').replace("'", "\\'")

        def double_quoted_wrapper(text):
            return text.replace('\\', '\\\\').replace('"', '\\"')

        grammar = r"""
                # Text before the current string.
                (
                    [^'"#]                                  |  # Not quoted characters.
                    '''  ([^'\\]|'(?!')|''(?!')|\\.])*  ''' |  # Inside single quoted triple strings
                    "" " ([^"\\]|"(?!")|""(?!^)|\\.])* "" " |  # Inside double quoted triple strings

                    \#[^\n]*(\n|$)           |  # Comment.
                    "(?!"") ([^"\\]|\\.)*"   |  # Inside double quoted strings.
                    '(?!'') ([^'\\]|\\.)*'      # Inside single quoted strings.

                        # Warning: The negative lookahead in the above two
                        #          statements is important. If we drop that,
                        #          then the regex will try to interpret every
                        #          triple quoted string also as a single quoted
                        #          string, making this exponentially expensive to
                        #          execute!
                )*
                # The current string that we're completing.
                (
                    ' (?P<var1>([^\n'\\]|\\.)*) |  # Inside a single quoted string.
                    " (?P<var2>([^\n"\\]|\\.)*)    # Inside a double quoted string.
                )
        """

        return compile_grammar(grammar,
                               escape_funcs={'var1': single_quoted_wrapper,
                                             'var2': double_quoted_wrapper,},
                               unescape_funcs={'var1': unwrapper,
                                               'var2': unwrapper,})

    def _complete_path_while_typing(self, document):
        char_before_cursor = document.char_before_cursor
        return document.text and (
            char_before_cursor.isalnum() or char_before_cursor in '/.~')

    def _complete_python_while_typing(self, document):
        char_before_cursor = document.char_before_cursor
        return document.text and (
            char_before_cursor.isalnum() or char_before_cursor in '_.')

    def get_completions(self, document, complete_event):
        """
        Get completions.
        """

        # Do Path completions
        if complete_event.completion_requested or self._complete_path_while_typing(
                document):
            for c in self._path_completer.get_completions(document,
                                                          complete_event):
                yield c

        # If we are inside a string, Don't do Jedi completion.
        if self._path_completer_grammar.match(document.text_before_cursor):
            return

        # Do custom word completions (only if the word is at the beginning of the line)
        if complete_event.completion_requested or self._complete_python_while_typing(
                document):
            for word in self.words:
                line_before_cursor = document.current_line_before_cursor
                if word.startswith(line_before_cursor):
                    yield Completion(word, -len(line_before_cursor),
                                     display_meta=self.words_metastring)

        # Do Jedi Python completions.
        if complete_event.completion_requested or self._complete_python_while_typing(
                document):
            script = _get_jedi_script_from_document(document, self.get_locals(),
                                                    self.get_globals())

            if script:
                try:
                    completions = script.completions()
                except TypeError:
                    # Issue #9: bad syntax causes completions() to fail in jedi.
                    # https://github.com/jonathanslenders/python-prompt-toolkit/issues/9
                    pass
                except UnicodeDecodeError:
                    # Issue #43: UnicodeDecodeError on OpenBSD
                    # https://github.com/jonathanslenders/python-prompt-toolkit/issues/43
                    pass
                except AttributeError:
                    # Jedi issue #513: https://github.com/davidhalter/jedi/issues/513
                    pass
                except ValueError:
                    # Jedi issue: "ValueError: invalid \x escape"
                    pass
                except KeyError:
                    # Jedi issue: "KeyError: u'a_lambda'."
                    # https://github.com/jonathanslenders/ptpython/issues/89
                    pass
                except IOError:
                    # Jedi issue: "IOError: No such file or directory."
                    # https://github.com/jonathanslenders/ptpython/issues/71
                    pass
                else:
                    for c in completions:
                        yield Completion(c.name_with_symbols,
                                         len(c.complete) - len(
                                             c.name_with_symbols),
                                         display=c.name_with_symbols)

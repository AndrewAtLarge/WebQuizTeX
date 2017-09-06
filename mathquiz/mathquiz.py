#!/usr/bin/env python3

r'''
-----------------------------------------------------------------------------------------
    mathquiz | Interactive on-line quizzes generated from LaTeX using python and TeX4ht
-----------------------------------------------------------------------------------------
    Copyright (C) Andrew Mathas and Donald Taylor, University of Sydney

    Distributed under the terms of the GNU General Public License (GPL)
                  http://www.gnu.org/licenses/

    This file is part of the Math_quiz system.

    <Andrew.Mathas@sydney.edu.au>
    <Donald.Taylor@sydney.edu.au>
-----------------------------------------------------------------------------------------
'''

# ---------------------------------------------------------------------------------------
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

import mathquiz_xml
from mathquiz_templates import *

# ---------------------------------------------------------------------------------------
# Return the full path for a file in the mathquiz directory
mathquiz_file = lambda file: os.path.join(os.path.dirname(os.path.realpath(__file__)),file)

# ---------------------------------------------------------------------------------------
class MetaData(dict):
    r"""
    A dummy class for reading, accessing and storing key-value pairs from a file

    Usage: MetaData(filename)
    """
    def __init__(self, filename):
        with open(filename,'r') as meta:
            for line in meta:
                if '=' in line:
                    key, val = line.strip().split('=')
                    if len(key.strip())>0:
                        setattr(self, key.strip().lower(), val.strip())

# read in basic meta data such as author, version, ...
metadata = MetaData(mathquiz_file('mathquiz.ini'))
metadata.debugging = False

# used to label the parts of questions as a, b, c, ...
alphabet = "abcdefghijklmnopqrstuvwxyz"

# this should no longer be necessary as we have switched to python 3
def strval(ustr):
    return ustr
    return ustr.encode('ascii','xmlcharrefreplace')

def MathQuizError(msg, err=None):
    r'''
    Consistent handling of errors in magthquiz: print the message `msg` and
    exist with error code `err.errno` if it is available.abs
    '''
    if err is None:
        print('MathQuiz error: {}'.format(msg))
    else:
        print('MathQuiz error: {}\n  {}'.format(msg, err))
    if metadata.debugging and err is not None:
        raise
    if hasattr(err, 'errno'):
        sys.exit(err.errno)
    sys.exit(1)

# ---------------------------------------------------------------------------------------
def main():
    # read settings from the mathquizrc file
    settings = MathQuizSettings()

    # parse the command line options
    parser = argparse.ArgumentParser(description = metadata.description,
                                     epilog      = mathquiz_help_message
    )
    parser.add_argument('quiz_file', nargs='*',type=str, default=None, help='latex quiz files')
    parser.add_argument('-l','--local', action='store', type=str, dest='local_page',
                        default=settings['mathquiz_local'], help='Local python code for generating the quiz web page '
    )
    parser.add_argument('-p', '--pst2pdf', action='store_true', default=False, 
                        help='Use pst2pdf to fix issues with images generated by pstricks')
    parser.add_argument('-s', '--shell-escape', action='store_true', default=False,
                        help='Shell escape for htlatex/make4ht')
    parser.add_argument('--initialise', action='store_true', default=False, help='Initialise files and setings for mathquiz')
    parser.add_argument('--settings', action='store_true', default=False, help='List system settings for mathquiz')
    parser.add_argument('--edit-settings', action='store_true', default=False, help='Edit mathquiz settings')
    parser.add_argument('--build', action='store', type=str, dest='mathquiz_mk4', default=settings['mathquiz_mk4'],
                        help='Build file for make4ht'
    )

    # not yet available
    parser.add_argument('-q', '--quiet', action='count', default=0, help='suppress tex4ht messages (also -qq etc)')

    # options suppressed from the help message
    parser.add_argument('--version', action = 'version', version = '%(prog)s {}'.format(metadata.version), help = argparse.SUPPRESS)
    parser.add_argument('--debugging', action = 'store_true', default = False, help = argparse.SUPPRESS)

    # parse the options
    options      = parser.parse_args()
    options.prog = parser.prog

    # set debugging mode from options
    metadata.debugging = options.debugging

    # initialise and exit
    if options.initialise:
        settings.initialise_mathquiz()
        sys.exit()

    # initialise and exit
    if options.settings:
        settings.list_settings()
        sys.exit()

    # initialise and exit
    if options.edit_settings:
        settings.initialise_mathquiz(edit_settings=True)
        sys.exit()

    # if no filename then exit
    if options.quiz_file==[]:
        parser.print_help()
        sys.exit(1)

    # import the local page formatter
    options.write_web_page = __import__(options.local_page).write_web_page

    options.initialise_warning = (settings['mathquiz_url'] == sms_http)

    # run through the list of quizzes and make them
    for quiz_file in options.quiz_file:
        if len(options.quiz_file)>1 and options.quiet<3:
            print('Making web page for {}'.format(quiz_file))
        # quiz_file is assumed to be a tex file if no extension is given
        if not '.' in quiz_file:
            quiz_file += '.tex'

        if not os.path.isfile(quiz_file):
            print('MathQuiz error: cannot read file {}'.format(quiz_file))

        else:
            # the file exists and is readable so make the quiz
            MakeMathQuiz(quiz_file, options, settings)

            quiz_file = quiz_file[:quiz_file.index('.')]  # remove the extension

            # move the css file into the directory for the quiz
            css_file = os.path.join(quiz_file, quiz_file+'.css')
            if os.path.isfile(quiz_file +'.css'):
                if os.path.isfile(css_file):
                    os.remove(css_file)
                shutil.move(quiz_file+'.css', css_file)

            # now clean up unless debugging
            if not options.debugging:
                for ext in [ '4ct', '4tc', 'dvi', 'idv', 'lg', 'log', 'ps', 'pdf', 'tmp', 'xref']:
                    if os.path.isfile(quiz_file +'.' +ext):
                        os.remove(quiz_file +'.' +ext)

                # files created when using pst2pdf
                if options.pst2pdf:
                    for file in glob.glob(quiz_file+'-pdf.*'):
                        os.remove(file)
                    for file in glob.glob(quiz_file+'-pdf-fixed.*'):
                        os.remove(file)
                    for extra in ['.preamble', '.plog', '-tmp.tex', '-pst.tex', '-fig.tex']:
                        if os.path.isfile(quiz_file+extra):
                            os.remove(quiz_file+extra)
                    if os.path.isdir(os.path.join(quiz_file,quiz_file)):
                        shutil.rmtree(os.path.join(quiz_file,quiz_file))

    if options.initialise_warning:
        print(mathquiz_url_warning)

#################################################################################
class MathQuizSettings(object):
    r'''
    Class for initialising mathquiz. This covers both reading and writting the mathquizrc file and
    copying files into the web directories during initialisation. The settings
    themselves are stored in attribute settings, which is a dictionary. The
    class reads and writes the settings to the mathquizrc file and the
    vbalues of the settings are available as items:
        >>> mq = MathQuizSettings()
        >>> mq['mathquiz_url']
        ... /MathQuiz
        >>> mq['mathquiz_url'] = '/new_url'
    '''

    # default of settings for the mathquizrc file - a dictionart of dictionaries
    # the 'help' field is for printing descriptions in the mathquizrc file
    settings = dict(
        mathquiz_local  = dict(val = 'mathquiz_local', help = 'A python module that writes the HTML page for the quiz' ),
        mathquiz_url    = dict(val = '/MathQuiz',      help = 'Relative URL for mathquiz web directory' ),
        mathquiz_dir    = dict(val = '',               help = 'Full path to MathQuiz web directory'),
        mathquiz_mk4    = dict(val = '',               help = 'Local build file for make4ht'),
        mathjax         = dict(val = '',               help = 'Local URL for mathjax'),
        department      = dict(val = '',               help = 'Department running quiz'),
        department_url  = dict(val = '',               help = 'URL for department running quiz'),
        institution     = dict(val = '',               help = 'University or institution'),
        institution_url = dict(val = '',               help = 'URL for university or institution'),
    )

    def __init__(self):
        '''
        If the mathquizrc file exists, which it may not, then read it.

        '''
        self.read_mathquizrc()

    def __getitem__(self, key):
        r'''
        Return the value of the corresponding setting. That is, it returns
            self.settings[key]['val']
        and an error if the key is unknown.
        '''
        if key in self.settings:
            return self.settings[key]['val']

        MathQuizError('unknown setting {} in mathquizrc.'.format(key))

    def __setitem__(self, key, val):
        r'''
        Set the value of the corresponding setting. This is the equivalent of
            self.settings[key]['val'] = val
        and an error if the key is unknown.
        '''
        if key in self.settings:
            self.settings[key]['val'] = val
        else:
            MathQuizError('unknown setting {} in mathquizrc'.format(key))

    def read_mathquizrc(self):
        r'''
        Read the settings in the mathquizrc file.

        By default, there is no mathquiz initialisation file. We first look for
        a .mathquizrc file in the users home directory and then look for a
        mathquizrc file in the mathquiuz source directory.
        '''

        if os.path.isfile(os.path.join(os.path.expanduser('~'),'.mathquizrc')):
            self.rc_file = os.path.join(os.path.expanduser('~'),'.mathquizrc')
        else:
            self.rc_file = mathquiz_file('mathquizrc')

        if os.path.isfile(self.rc_file):
            try:
                with open(self.rc_file, 'r') as mathquizrc:
                    for line in mathquizrc:
                        if '%' in line:  # remove comments
                            line = line[:line.index('#')]
                        if '=' in line:
                            key, val = line.split('=')
                            key = key.strip().lower()
                            val = val.strip()
                            if key in self.settings and val != '':
                                self[key] = val
                            elif len(key)>0:
                                MathQuizError('unknown setting {} in mathquizrc'.format(key))

            except Exception as err:
                MathQuizError('there was an error reading the mathquizrc file,', err)

    def write_mathquizrc(self):
        r'''
        Write the settings to the mathquizrc file. This method is only called
        from initialise_mathquiz, which should only be called when MathQuiz
        is being set up initially.
        '''
        try:
            with open(self.rc_file, 'w') as rc_file:
                for key in self.settings:
                    if self[key] != '':
                        rc_file.write('# {}\n{:<14} = {}\n'.format(self.settings[key]['help'], key, self[key]))

        except PermissionError as err:
                MathQuizError(permission_error.format(self.rc_file), err)

        except Exception as err:
            MathQuizError('there was an error writing the mathquizrc file,', err)

    def list_settings(self):
        r'''
        Print the non-default settings for mathquiz from the mathquizrc
        '''
        print('MathQuiz settings stored in {}\n'.format(self.rc_file))
        for key in self.settings:
            if self[key] != '':
                print('  # {}\n  {:<14} = {}\n'.format(self.settings[key]['help'], key, self[key]))

    def initialise_mathquiz(self, edit_settings=False):
        r'''
        Set the root for the MathQuiz web directory and copy the www files
        into this directory. Once this is done save the settings to
        mathquizrc.
        '''
        print(initialise_introduction)

        # prompt for directory and copy files - are these reasonable defaults
        # for each OS?
        if len(self['mathquiz_dir']) > 0:
            web_root = self['mathquiz_dir']
        elif sys.platform == 'linux':
            web_root = '/usr/local/httpd/MathQuiz'
        elif sys.platform == 'darwin':
            web_root = '/Library/WebServer/Documents/MathQuiz'
        else:
            web_root = '/Local/Library/WebServer'

        import readline
        web_dir = input(web_directory_message.format(web_root))
        if web_dir == '':
            web_dir = web_root
        if web_dir == 'SMS':
            # undocumented: allow links to SMS web pages
            self['mathquiz_dir'] = 'SMS'
            self['mathquiz_url'] =  sms_http
        elif not os.path.isdir(web_dir):
            files_copied = False
            while not files_copied:
                try:
                    # first delete files of the form mathquiz.* files in web_dir
                    for file in glob.glob(os.path.join(web_dir, 'mathquiz.*')):
                        os.remove(file)
                    # ... now remove the doc directory
                    web_doc = os.path.join(web_dir, 'doc')
                    if os.path.isfile(web_doc) or os.path.islink(web_doc):
                        os.remove(web_doc)
                    elif os.path.isdir(web_doc):
                        shutil.rmtree(web_doc)

                    if os.path.isdir(mathquiz_file('www')):
                        # if the www directory exists then copy it to web_dir
                        shutil.copytree('www', web_dir)
                    else:
                        # assume this is a development version and add links
                        # from the web directory to the parent directory
                        if not os.path.exists(web_dir):
                            os.makedirs(web_dir)
                        # get the root directory of the source code
                        mathquiz_src = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
                        for (src, target) in [('javascript/mathquiz.js', 'mathquiz.js'),
                                              ('css/mathquiz.css', 'mathquiz.css'),
                                              ('doc', 'doc')]:
                            os.symlink(os.path.join(mathquiz_src, src), os.path.join(web_dir, target))

                    self['mathquiz_dir'] = web_dir
                    files_copied = True

                except PermissionError as err:
                    MathQuizError(permission_error.format(web_dir), err)

                except Exception as err:
                    print('There was a problem copying files to {}.\n  Please give a different directory.\n[Error: {}]\n'.format(web_dir, err))
                    web_dir = input('Full path to MathQuiz web directory: ')

            # now prompt for the relative url
            mq_url = input(mathquiz_url_message.format(self['mathquiz_url']))
            if mq_url != '':
                if not web_dir.ends_with(mq_url):
                    MathQuizError('{} does not end with {}.'.format(web_dir, mq_url))

                # removing trailing slashes from mq_url
                while mq_url[-1] == '/':
                    mq_url = mu_url[:len(mq_url)-1]
                self.mathquizrc['mathquiz_url'] = mq_url

        if edit_settings:
            print(edit_settings)
            for key in self.settings:
                if key not in ['mathquiz_dir', 'mathquiz_url']:
                    setting = input('{}{}: '.format(self.settings[key]['help'],
                        '' if self[key] == '' else ' ['+self[key]+']')
                    )
                    if setting != '':
                        self[key] = setting

        # save the settings and exit
        self.write_mathquizrc()
        if edit_settings:
            self.list_settings()
        else:
            print(initialise_ending)

#################################################################################
class MakeMathQuiz(object):
    """
    Convert a mathquiz latex file to an on-line quiz.

    There are several steps:
      1. If given a LaTeX file then run htlatex/make4ht on the latex file to generate an
         xml file for the quiz that has all LaTeS markup converted to html.
      2. Read in the xml file version of the quiz
      3. Spit out the html version

    The HTMl is contructed using the template strings in mathquiz_templates
    """
    # attributes that will form part of the generated web page
    header=''         # everything printed in the page header: meta data, includes, javascript, CSS, ...
    css=''            # css specifications
    javascript=''     # javascript code
    quiz_questions='' # the main quiz page
    side_menu=''      # the left hand quiz menu

    def __init__(self, quiz_file, options, settings):
        self.options = options
        self.settings = settings
        self.quiz_file, extension = quiz_file.split('.')
        self.mathquiz_url = settings['mathquiz_url']

        # run htlatex only if quiz_file has a .tex extension
        if extension == 'tex':
            self.htlatex_quiz_file()

        if self.options.quiet<2:
            print('MathQuiz generating web page for {}'.format(self.quiz_file))

        self.read_xml_file()

        self.dTotal = len(self.quiz.discussion_list)
        self.qTotal = len(self.quiz.question_list)

        # generate the variuous components ofthe web page
        self.course = self.quiz.course
        self.school = self.quiz.school
        for opt in ['department', 'department_url', 'institution', 'institution_url']:
            if settings[opt] != '':
                self.school[opt] = settings[opt]

        self.title = self.quiz.title
        self.add_meta_data()
        self.add_question_javascript()
        self.add_side_menu()
        self.add_quiz_header_and_questions()

        if any(['???' in self.course[key] for key in ['name', 'code', 'url','quizzes_url']]):
            # don't add bread crumbs if we are missing important information
            self.bread_crumbs = ''
        else:
            self.bread_crumbs = bread_crumbs.format(
                    title=self.title, 
                    bread_crumb=self.quiz.bread_crumb, 
                    code = self.course['code'],
                    url = self.course['url'],
                    quizzes_url = self.course['quizzes_url'],
                    department = self.school['department'],
                    department_url = self.school['department_url']
            )

        # now write the quiz to the html file
        with open(self.quiz_file+'.html', 'w') as file:
            # write the quiz in the specified format
            file.write( self.options.write_web_page(self) )

    def htlatex_quiz_file(self):
        r'''
        Process the file using htlatex/make4ht. This converts the quiz to an xml
        with markup specifying the different elements of the quiz page.
        '''
        # run() is a shorthand for executing system commands depending on the quietness
        #       we need to use shell=True because otherwise pst2pdf gives an error
        # talk() is a shorthand for letting the user know what is happening
        if self.options.quiet == 0:
            run  = lambda cmd: subprocess.call(cmd, shell=True)
            talk = lambda msg: print(msg)
        elif self.options.quiet == 1:
            run  = lambda cmd: subprocess.call(cmd, shell=True, stdout=open(os.devnull, 'wb'))
            talk = lambda msg: print(msg)
        else:
            run  = lambda cmd: subprocess.call(cmd, shell=True, stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))
            talk = lambda msg: None

        # at the minimum we put a css file into a <quiz_file> subdirectory
        if not os.path.exists(self.quiz_file):
            os.makedirs(self.quiz_file)

        # as we may need to preprocess quiz_file with pst2pdf we allow ourselves to change it name
        q_file = self.quiz_file

        # set pst2pdf = True if pst2pdf is given as an option to the mathquiz documentclass
        with open(self.quiz_file+'.tex', 'r') as quiz_file:
            doc = quiz_file.read()
        try:
            brac = doc.index(r'\documentclass[') + 15 # start of class options
            if 'pst2pdf' in [ opt.strip() for opt in doc[brac:brac+doc[brac:].index(']')].split(',')]:
                self.options.pst2pdf = True
        except ValueError:
            pass

        # preprocess the latex file with pst2pdf if requested
        if self.options.pst2pdf:
            talk('Preprocessing {} with pst2pdsf'.format(q_file))
            try:
                # pst2pdf converts pspicture environments to svg images and makes a
                # new latex file q_file+'-pdf' that includes these
                cmd='pst2pdf --svg --imgdir={q_file} {q_file}.tex'.format(q_file=q_file)
                run(cmd)
            except OSError as err:
                if err.errno == os.errno.ENOENT:
                    MathQuizError('pst2pdf not found. You need to install pst2pdf to use the --pst2pdf option', err)
                else:
                    MathQuizError('error running pst2pdf on {}'.format(q_file), err)

            # match \includegraphics commands
            fix_svg = re.compile(r'(\\includegraphics\[scale=1\])\{('+ q_file+r'-fig-[0-9]*)\}')
            # the svg images are in the q_file subdirectory but latex can't
            # find them so we update the tex file to look in the right place
            try:
                with open(q_file+'-pdf.tex','r') as pst_file:
                    with open(q_file+'-pdf-fixed.tex', 'w') as pst_fixed:
                        # tell pst_fixed where it came from
                        pst_fixed.write(r'\makeatletter\def\MQ@quizfile{%s.tex}\makeatother' % self.quiz_file)
                        for line in pst_file:
                            pst_fixed.write(fix_svg.sub(r'\1{%s/\2.svg}'%self.quiz_file, line))
            except IOError as err:
                MathQuizError('there was an problem running pst2pdf for {}'.format(q_file), err)

            q_file = q_file + '-pdf-fixed'

        try:
            talk('Processing {}.tex with TeX4ht'.format(q_file))
            cmd='make4ht --utf8 --config mathquiz.cfg {build} {escape} {q_file}.tex'.format(
                    q_file = q_file,
                    build  = '--build-file {} '.format(self.options.mathquiz_mk4) if self.options.mathquiz_mk4 !='' else '',
                    escape = '--shell-escape' if self.options.shell_escape else ''
            )
            run(cmd)

            # move the css file into the quiz_file subdirectory
            if os.path.exists(q_file+'.css'):
                shutil.move(q_file+'.css', os.path.join(self.quiz_file, self.quiz_file+'.css'))

            # Now move any images that were created into the quiz_file
            # subdirectory and update the links in the html file As htlatex
            # generates an html file, we rename this as an xml file at the same
            # time - in the cfg file, \Preamable{ext=xml} should lead to an xml
            # file being created but this doesn't seem to work ??
            try:
                fix_img = re.compile(r'^src="('+q_file+r'[0-9]*x\....)" (alt="PIC" .*)$')
                with open(q_file+'.html','r') as make4ht_file:
                    with open(self.quiz_file+'.xml', 'w') as xml_file:
                        for line in make4ht_file:
                            match = fix_img.match(line)
                            if match is None:
                                xml_file.write(line)
                            else:
                                # update html link and move file
                                image, rest_of_line = match.groups()
                                xml_file.write(r'src="{}/{}" {}'.format(self.quiz_file, image, rest_of_line))
                                shutil.move(image, os.path.join(self.quiz_file, image))

            except IOError as err:
                MathQuizError('there was a problem moving the image files for {}'.format(self.quiz_file), err)

        except Exception as err:
            MathQuizError('something whent wrong when running htlatex on {}'.format(self.quiz_file), err)

    def read_xml_file(self):
        r'''
        Read in the mathquiz xml file for the quiz and store the xml document
        tree in ``self.quiz``.
        '''
        try:
            # read in the xml version of the quiz
            if not os.path.isfile(self.quiz_file+'.xml'):
                MathQuizError('{}.xml does not exist!?'.format(self.quiz_file))
            self.quiz = mathquiz_xml.ReadMathQuizXmlFile(self.quiz_file+'.xml', self.options.debugging)
        except Exception as err:
            MathQuizError('error reading the xml generated for {}. Please check your latex source.'.format(self.quiz_file), err)

    def add_meta_data(self):
        """ add the meta data for the web page to self.header """
        # meta tags`
        self.header += html_meta.format(version     = metadata.version,
                                        authors     = metadata.authors,
                                        mathquiz_url = self.mathquiz_url,
                                        description = metadata.description,
                                        copyright   = metadata.copyright,
                                        department  = self.school['department'],
                                        institution  = self.school['institution'],
                                        quiz_file   = self.quiz_file)

        # we don't need any of the links or metas from the latex file
        # self.header += ''.join('  <meta {}>\n'.format(' '.join('{}="{}"'.format(k,meta[k]) for k in meta)) for meta in self.quiz.meta_list)
        # self.header += ''.join('  <link {}>\n'.format(' '.join('{}="{}"'.format(k,link[k]) for k in link)) for link in self.quiz.link_list)

    def add_side_menu(self):
        """ construct the left hand quiz menu """
        if len(self.quiz.discussion_list)>0: # links for discussion items
            discussion_list = '\n       <ul>\n   {}\n       </ul>'.format(
                  '\n   '.join(discuss.format(b=q+1, title=d.short_heading) for (q,d) in enumerate(self.quiz.discussion_list)))
        else:
            discussion_list = ''

        buttons = '\n'+'\n'.join(button.format(b=q, cls=' button-selected' if len(self.quiz.discussion_list)==0 and q==1 else '')
                                   for q in range(1, self.qTotal+1))

        if self.school['department_url']=='':
            department = self.school['department']
        else:
            department = '''<a href="{department_url}">{department}</a>'''.format(**self.school)

        if self.school['institution_url']=='':
            institution = self.school['institution']
        else:
            institution = '''<a href="{institution_url}">{institution}</a>'''.format(**self.school)

        # end of progress buttons, now for the credits
        self.side_menu = side_menu.format(discussion_list=discussion_list, 
                                          buttons=buttons, 
                                          version=metadata.version,
                                          department=department,
                                          institution=institution,
        )

    def add_question_javascript(self):
        """ Add the javascript for the questions to self and write the
        javascript initialisation file, <quiz>/quiz_list.js, for the quiz.
        When the quiz page load, MathQuizInit read the quiz_list initialisation
        file to load the answers to ythe question and tyhe discussino item
        headers. We don't explsit list quiz_list.js in the page headers
        because we want to hide this information from the stduent, although
        they can easily get this if they open by the javascript console and
        know what to look for.
        """

        try:
            os.makedirs(self.quiz_file, exist_ok=True)
            with open(os.path.join(self.quiz_file,'quiz_list.js'), 'w') as quiz_list:
                if self.qTotal>0:
                    for (i,d) in enumerate(self.quiz.discussion_list):
                        quiz_list.write('Discussion[{}]="{}";\n'.format(i, d.heading))
                if self.qTotal >0:
                    for (i,q) in enumerate(self.quiz.question_list):
                        quiz_list.write('QuizSpecifications[%d]=new Array();\n' % i)
                        a = q.answer
                        if isinstance(a,mathquiz_xml.Answer):
                             quiz_list.write('QuizSpecifications[%d].value="%s";\n' % (i,a.value))
                             quiz_list.write('QuizSpecifications[%d].type="input";\n' % i)
                        else:
                             quiz_list.write('QuizSpecifications[%d].type="%s";\n' % (i,a.type))
                             quiz_list.write(''.join('QuizSpecifications[%d][%d]=%s;\n' % (i,j,s.expect) for (j,s) in enumerate(a.item_list)))

        except Exception as err:
            MathQuizError('error writing quiz specifications', err)

        self.javascript = questions_javascript.format(
                              mathquiz_url = self.mathquiz_url,
                              mathjax = mathjax if self.settings['mathjax'] == '' else self.settings['mathjax']
        )
        self.mathquiz_init = mathquiz_init.format(
                              qTotal = self.qTotal,
                              dTotal = self.dTotal,
                              quiz_file = self.quiz_file,
        )

    def add_quiz_header_and_questions(self):
        r'''
        Write the quiz head and the main body of the quiz.
        '''
        if self.qTotal == 0:
            arrows = ''
        else:
            arrows = navigation_arrows.format(subheading='Question 1' if self.dTotal==0 else 'Discussion')

        # specify the quiz header - this will be wrapped in <div class="question_header>...</div>
        self.quiz_header=quiz_header.format(title=self.title,
                                      initialise_warning=initialise_warning if self.options.initialise_warning else '',
                                      question_number=self.quiz.discussion_list[0].heading if len(self.quiz.discussion_list)>0 else
                                                      'Question 1' if len(self.quiz.question_list)>0 else '',
                                      arrows = arrows
        )

        # now comes the main page text
        # discussion(s) masquerade as negative questions
        if len(self.quiz.discussion_list)>0:
          dnum = 0
          for d in self.quiz.discussion_list:
            dnum+=1
            self.quiz_questions+=discussion.format(dnum=dnum, discussion=d,
                               display='style="display: table;"' if dnum==1 else '',
                               input_button=input_button if len(self.quiz.question_list)>0 and dnum==len(self.quiz.discussion_list) else '')

        # index for quiz
        if len(self.quiz.quiz_list)>0:
          # add index to the web page
          self.quiz_questions+=quiz_list.format(
                 course=self.course['name'],
                 quiz_index='\n          '.join(quiz_list_item.format(url=q['url'], title=q['title'])
                                                for q in self.quiz.quiz_list)
          )
          # write a javascript file for displaying the menu
          # quizmenu = the index file for the quizzes in this directory
          with open('quiztitles.js','w') as quizmenu:
             quizmenu.write('var QuizTitles = [\n{titles}\n];\n'.format(
                 titles = ',\n'.join("  ['{}', '{}/Quizzes/{}']".format(
                                     q['title'],
                                     self.course['url'],
                                     q['url']) for q in self.quiz.quiz_list
                                    )
                 )
             )

        # finally we print the quesions
        if len(self.quiz.question_list)>0:
          self.quiz_questions+=''.join(question_wrapper.format(qnum=qnum+1,
                                                display='style="display: table;"' if qnum==0 and len(self.quiz.discussion_list)==0 else '',
                                                question=self.print_question(q,qnum+1),
                                                response=self.print_responses(q,qnum+1))
                                for (qnum,q) in enumerate(self.quiz.question_list)
          )

    def print_question(self, Q, Qnum):
        r'''Here:
            - Q is a class containing the question
            - Qnum is the number of the question
        '''
        if isinstance(Q.answer,mathquiz_xml.Answer):
            options=input_answer.format(tag=Q.answer.tag if Q.answer.tag else '')
        else:
            options=choice_answer.format(choices='\n'.join(self.print_choices(Qnum, Q.answer.item_list, choice) for choice in range(len(Q.answer.item_list))))
                                        #hidden=input_single.format(qnum=Qnum) if Q.answer.type=="single" else '')
        return question_text.format(qnum=Qnum, question=Q.question, question_options=options)

    def print_choices(self, qnum, answers, choice):
        r'''
        Here:
            - qnum     = question number
            - answers = listr of answers to this question
            - choice  = number of the option we need to process.
        We put the parts into ans.parent.cols multicolumn format, so we have
        to add '<tr>' and '</tr>' tags depending on choice.
        '''
        ans = answers[choice]
        item  ='<tr>' if ans.parent.cols==1 or (choice % ans.parent.cols)==0 else '<td>&nbsp;</td>'
        if ans.parent.type == 'single':
            item+=single_item.format(choice=alphabet[choice], qnum=qnum, answer=ans.answer)
        elif ans.parent.type == 'multiple':
            item+=multiple_item.format(choice=alphabet[choice], qnum=qnum, optnum=choice, answer=ans.answer)
        else:
            item+= '<!-- internal error: %s -->\n' % ans.parent.type
            sys.stderr.write('Unknown question type encountered: {}'.format(ans.parent.type))
        if ans.parent.cols == 1 or (choice+1) % ans.parent.cols == 0 or choice == len(answers)-1:
            item+= '   </tr><!-- choice={}, cols={}, # answers = {} -->\n'.format(choice, ans.parent.cols, len(answers))
        return item

    def print_responses(self,question,qnum):
        r'''
        Generate the HTML for displaying the response help text when the user
        answers a question.
        '''
        if isinstance(question.answer,mathquiz_xml.Answer):
            s = question.answer
            response  = tf_response_text.format(choice=qnum, response='true', answer='Correct!', answer2='', text=s.when_right)
            response += tf_response_text.format(choice=qnum, response='false', answer='Incorrect.', answer2='Please try again.', text=s.when_wrong)
        elif question.answer.type == "single":
            response='\n'+'\n'.join(single_response.format(qnum=qnum, part=snum+1,
                                                      answer='correct! ' if s.expect=='true' else 'incorrect ',
                                                      alpha=alphabet[snum],
                                                      response=s.response)
                                for (snum, s) in enumerate(question.answer.item_list)
            )
        else: # question.answer.type == "multiple":
            response='\n'+'\n'.join(multiple_response.format(qnum=qnum, part=snum+1,alpha=alphabet[snum], answer=s.expect.capitalize(), response=s.response)
                                for (snum, s) in enumerate(question.answer.item_list)
            )
            response+=multiple_response_correct.format(qnum=qnum,
                responses='\n'.join(multiple_response_answer.format(answer=s.expect.capitalize(), reason=s.response) for s in question.answer.item_list)
            )
        return '<div class="answer">'+response+'</div>'

# =====================================================
if __name__ == '__main__':
    main()

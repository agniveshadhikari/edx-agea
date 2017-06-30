
import datetime
import hashlib
import json
import logging
import mimetypes
import os
import pkg_resources
import pytz
import grades

from functools import partial

from courseware.models import StudentModule

from django.core.exceptions import PermissionDenied
from django.core.files import File
from django.core.files.storage import default_storage
from django.conf import settings
from django.template import Context, Template

from student.models import user_by_anonymous_id
from submissions import api as submissions_api
from submissions.models import StudentItem as SubmissionsStudent

from webob.response import Response

from xblock.core import XBlock
from xblock.exceptions import JsonHandlerError
from xblock.fields import Dict, Scope, String, Float, Integer
from xblock.fragment import Fragment
from file_storage import save_file

import storage

from xmodule.util.duedate import get_extended_due_date

from grader import *


log = logging.getLogger(__name__)
BLOCK_SIZE = 8 * 1024
FORCE_EVAL_EVERYTIME = True
IMAGEDIFF_ROOT = "/edx/var/edxapp/media/"

def reify(meth):
   
    def getter(inst):
   
        value = meth(inst)
        inst.__dict__[meth.__name__] = value
        return value
    return property(getter)


class ExcelSheetAssessmentXBlock(XBlock):
    has_score = True
    icon_class = 'problem'
    STUDENT_FILEUPLOAD_MAX_SIZE = 4 * 1000 * 1000  # 4 MB

    display_name = String(
        display_name = 'Block Type',
        default='Excel Sheet Assessment', scope=Scope.settings,
        help="This is the question title."

    )

    question = String(
        display_name = "Question text",
        default='Your Question Statement appears here', scope=Scope.settings,
        help="This is the question text that is shown to the student alongside the "
             "uploaded question file."
    )
    
    title = String(
        display_name = "Question title",
        default='Your Question Title appears here', scope=Scope.settings,
        help="This is the question title that appears at the top of the problem"
    )

    weight = Float(
        display_name="Problem Weight",
        help=("Defines the number of points each problem is worth. "
              "If the value is not set, the problem is worth the sum of the "
              "option point values."),
        default=1.0,
        values={"min": 1, "step": .1},
        scope=Scope.settings
    )

    points = Integer(
        display_name = "Maximum score",
        help = "The minimum score to be obtained by the student to be given full credit.",
        default=100,
        scope=Scope.settings
    )

    score = Integer(
        display_name="Score assigned by autograder",
        help = "Absolute score assigned by the autograder",
        default=None,
        scope=Scope.user_state
    )

    attempts = Integer(
        display_name = "No of attempts",
        help=("Number of attempts taken by the student on this problem."),
        default=0,
        scope=Scope.user_state)

    max_attempts = Integer(
        display_name=("Maximum attempts permitted"),
        help=("Defines the number of times a student can try to answer this problem. "
               "If the value is not set, infinite attempts are allowed."),
        scope=Scope.settings
    )

    raw_answer=Dict(
        default={},
        help=("Dict internally used to store the sha1, mimetype, filename of the last uploaded assignment"),
        scope=Scope.user_state
    )
    
    raw_question=Dict(
        default={},
        help=("Dict internally used to store the sha1, mimetype, filename of the last uploaded question"),
        scope=Scope.settings
    )

    raw_solution=Dict(
        default={},
        help=("Dict internally used to store the sha1, mimetype, filename of the last uploaded solution"),
        scope=Scope.settings
    )

    def max_score(self):
    
        return self.points

    @reify
    def block_id(self):
       return self.scope_ids.usage_id

    def get_submission(self):
        """
        Returns the raw_answer dictionary
        """
        submissions = self.raw_answer
        if submissions is not None:
            return {
                "answer": self.raw_answer
            }
           
    def get_question(self):
        """
        Returns the raw_question dictionary
        """
        question = self.raw_question
        if question is not None:
            return {
                "question": self.raw_question
            }

    def get_solution(self):
        """
        Returns the raw_solution dictionary   
        """
        solution = self.raw_solution
        if solution is not None:
            return {
                "solution": self.raw_solution
            }
 
    def student_view(self, context=None):
        # pylint: disable=no-member
        """
        Student view, renders the content of LMS
        """
        context = {
            "student_state": json.dumps(self.student_state()),
            "id": self.location.name.replace('.', '_'),
            "max_file_size": getattr(
                settings, "STUDENT_FILEUPLOAD_MAX_SIZE",
                self.STUDENT_FILEUPLOAD_MAX_SIZE
            )
        }
        fragment = Fragment()
        fragment.add_content(
            render_template(
                'templates/assignment/show.html',
                context
            )
        )
        fragment.add_javascript(_resource("static/js/src/agea.js"))
        fragment.add_javascript(_resource("static/js/src/jquery.tablesorter.min.js"))
        fragment.initialize_js('ExcelSheetAssessmentXBlock')
        return fragment
 
    def student_state(self):
        """
        Returns the context for rendering the student view in the form of a dictionary
        """
        submission = self.get_submission()
        if submission:
            uploaded_submission = submission.get("answer").get("filename", None)
            if uploaded_submission:
                uploaded = {"filename": submission['answer']['filename']}
            else:
                uploaded = None
        else:
            uploaded = None

        
       
        
        return {
            "display_name": self.title,
            "question":self.question,
            "uploaded": uploaded,
            "raw_answer":self.raw_answer,
            "raw_question":self.raw_question,
            "score": self.score,
            "weight":self.weight,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
        }

    def studio_state(self):
        """
        Returns the context for rendering the studio view in the form of a dictionary
        """
        submission = self.get_question()
        if submission:
            uploaded_submission = submission.get("question").get("filename", None)
            if uploaded_submission:
                quploaded = {"filename": submission['question']['filename']}
            else:
                quploaded = None
        else:
            quploaded = None
        
        submission = self.get_solution()
        if submission:
            uploaded_submission = submission.get("solution").get("filename", None)
            if uploaded_submission:
                suploaded = {"filename": submission['solution']['filename']}
            else:
                suploaded = None
        else:
            suploaded = None


        return {
            "display_name": self.title,
            "question":self.question,
            "uploaded": quploaded,
            "suploaded":suploaded,
            "raw_question" : self.raw_question,
            "solutionUploaded": suploaded,
            "raw_soluion": self.raw_solution,
            "weight":self.weight
        }
    
    def studio_view(self, context=None):
        """
        Studio view, renders the content of CMS
        """
        cls = type(self)

        def none_to_empty(data):
            return data if data is not None else ''
        edit_fields = (
            (field, none_to_empty(getattr(self, field.name)), validator)
            for field, validator in (
                (cls.title, 'string'),
                (cls.question,'string'),
                (cls.points, 'number'),
                (cls.weight, 'number'),
                (cls.max_attempts, 'number')
            )
        )
        context = {
            "studio_state": json.dumps(self.studio_state()),

            "id": self.location.name.replace('.', '_'),
            "max_file_size": getattr(
                settings, "STUDENT_FILEUPLOAD_MAX_SIZE",
                self.STUDENT_FILEUPLOAD_MAX_SIZE,
            ),
            
            'fields': edit_fields    
            
            
        }
        fragment = Fragment()
        fragment.add_content(
            render_template(
                'templates/assignment/edit.html',
                context
            )
        )
        fragment.add_css(_resource("static/css/agea.css"))
        fragment.add_javascript(_resource("static/js/src/studio.js"))

        fragment.add_javascript(_resource("static/js/src/jquery.tablesorter.min.js"))
        fragment.initialize_js('ExcelSheetAssessmentXBlock')
        return fragment

    @XBlock.json_handler
    def save_agea(self, data, suffix=''):
        """
        Persist block data when updating settings in studio.
        """
        self.title = data.get('title', self.title)
        self.question = data.get('question', self.question)
        self.raw_question = data.get('raw_question',self.raw_question)
        self.raw_solution= data.get('raw_solution',self.raw_solution)
        self.max_attempts = data.get('max_attempts', self.max_attempts)
        # Validate points before saving
        points = data.get('points', self.points)
        # Check that we are an int
        try:
            points = int(points)
        except ValueError:
            raise JsonHandlerError(400, 'Points must be an integer')
        # Check that we are positive
        if points < 0:
            raise JsonHandlerError(400, 'Points must be a positive integer')
        self.points = points

        # Validate weight before saving
        
        weight = data.get('weight', self.weight)
        # Check that weight is a float.
        if weight:
            try:
                weight = float(weight)
            except ValueError:
                raise JsonHandlerError(400, 'Weight must be a decimal number')
            # Check that we are positive
            if weight < 0:
                raise JsonHandlerError(
                    400, 'Weight must be a positive decimal number'
                )
        self.weight = weight      
        self.save()
        
        #self.weight = data.get('weight', self.max_score())

    @XBlock.handler
    def upload_assignment(self, request, suffix=''):
        """
        Uploads the student file on local disk, then calls storage api, grades the file, and then deletes the file from local disk
        """
        upload = request.params['assignment']
        sha1 = _get_sha1(upload.file)
        answer = {
            "sha1": sha1,
            "filename": upload.file.name,
            "mimetype": mimetypes.guess_type(upload.file.name)[0]
        }

        self.raw_answer = answer
        path = self._file_storage_path(sha1, upload.file.name)
        
        filepathexists=os.path.join(IMAGEDIFF_ROOT, path)
        file_exists=os.path.exists(filepathexists)
        if  not file_exists:
            save_file(path, File(upload.file))
            file_exists=True
        try:
            storage.store_data(str(self.course_id), str(self.xmodule_runtime.anonymous_student_id), str(self.location.block_id), file(IMAGEDIFF_ROOT + path))
        except PersonValueError:
            log.info("storage api upload failed:")
            log.info("peson argument cant be an empty string")
        except DepartmentValueError:
            log.info("storage api upload failed:")
            log.info("department argument cant be an empty string")
        except QualifierValueError:
            log.info("storage api upload failed:")
            log.info("qualifier argument cant be an empty string")
        except BucketValueError:
            log.info("storage api upload failed:")
            log.info("invalid bucket key argument")
        except S3ValueError:
            log.info("storage api upload failed:")
            log.info("invalid S3 credentials")
        except SocketValueError:
            log.info("storage api upload failed:")
            log.info("invalid host")
        self.grade_this_guy()
        self.attempts += 1
        os.remove(IMAGEDIFF_ROOT + path) 
        return Response(json_body=self.student_state())

    @XBlock.handler
    def upload_question(self, request, suffix=''):
        """
        Uploads the question file on local disk, then calls storage api
        """
        qupload = request.params['qassignment'] 
        sha1 = _get_sha1(qupload.file)
        question = {
            "sha1": sha1,
            "filename": qupload.file.name,
            "mimetype": mimetypes.guess_type(qupload.file.name)[0]
        }

        self.raw_question = question

        path = self._question_storage_path(sha1, qupload.file.name)

        
        filepathexists=os.path.join(IMAGEDIFF_ROOT, path)
        file_exists=os.path.exists(filepathexists)
        if  not file_exists:
            save_file(path, File(qupload.file))
            file_exists=True


        try:
            storage.store_data(str(self.course_id), "question", str(self.location.block_id), file(IMAGEDIFF_ROOT + path))
        except PersonValueError:
            log.info("storage api upload failed:")
            log.info("peson argument cant be an empty string")
        except DepartmentValueError:
            log.info("storage api upload failed:")
            log.info("department argument cant be an empty string")
        except QualifierValueError:
            log.info("storage api upload failed:")
            log.info("qualifier argument cant be an empty string")
        except BucketValueError:
            log.info("storage api upload failed:")
            log.info("invalid bucket key argument")
        except S3ValueError:
            log.info("storage api upload failed:")
            log.info("invalid S3 credentials")
        except SocketValueError:
            log.info("storage api upload failed:")
            log.info("invalid host")


   
        self.save()
            
        return Response(json_body=self.studio_state())

    @XBlock.handler
    def upload_solution(self, request, suffix=''):
        """
        Uploads the solution file on local disk, then calls storage api
        """
        upload = request.params['sassignment']
        sha1 = _get_sha1(upload.file)
        solution = {
            "sha1": sha1,
            "filename": upload.file.name,
            "mimetype": mimetypes.guess_type(upload.file.name)[0]
        }
        # del xbl
        #student_id = self.student_submission_id()

        #add xbla update IITBsub
        self.raw_solution = solution

        # IITBombayX zip changes
        #submis = submissions_api.create_submission(student_id, answer)
        path = self._solution_storage_path(sha1, upload.file.name)
        
        filepathexists=os.path.join(IMAGEDIFF_ROOT, path)
        file_exists=os.path.exists(filepathexists)
        if  not file_exists:
            save_file(path, File(upload.file))
            file_exists=True


        try:
            storage.store_data(str(self.course_id), "solution", str(self.location.block_id), file(IMAGEDIFF_ROOT + path))
        except PersonValueError:
            log.info("storage api upload failed:")
            log.info("peson argument cant be an empty string")
        except DepartmentValueError:
            log.info("storage api upload failed:")
            log.info("department argument cant be an empty string")
        except QualifierValueError:
            log.info("storage api upload failed:")
            log.info("qualifier argument cant be an empty string")
        except BucketValueError:
            log.info("storage api upload failed:")
            log.info("invalid bucket key argument")
        except S3ValueError:
            log.info("storage api upload failed:")
            log.info("invalid S3 credentials")
        except SocketValueError:
            log.info("storage api upload failed:")
            log.info("invalid host")



        self.save()       
        return Response(json_body=self.studio_state())

    @XBlock.handler
    def download_assignment(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Downloads the student's answer file from storage api and then returns a response
        """
        try:
            file_descriptor = storage.access_data(str(self.course_id),str(self.xmodule_runtime.anonymous_student_id), str(self.location.block_id))
        except PersonValueError:
            log.info("storage api download failed:")
            log.info("peson argument cant be an empty string")
        except DepartmentValueError:
            log.info("storage api download failed:")
            log.info("department argument cant be an empty string")
        except QualifierValueError:
            log.info("storage api download failed:")
            log.info("qualifier argument cant be an empty string")
        except BucketValueError:
            log.info("storage api download failed:")
            log.info("invalid bucket key argument")
        except S3ValueError:
            log.info("storage api download failed:")
            log.info("invalid S3 credentials")
        except SocketValueError:
            log.info("storage api download failed:")
            log.info("invalid host")

        

        app_iter = iter(partial(file_descriptor.read, BLOCK_SIZE), '')

        return Response(
            app_iter=app_iter,
            content_type=self.raw_answer["mimetype"],
            content_disposition="attachment; filename=" + self.raw_answer["filename"].encode('utf-8'))

    @XBlock.handler
    def download_question(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Downloads the question file from storage api and then returns a response
        """
        try:
            file_descriptor = storage.access_data(str(self.course_id), "question", str(self.location.block_id))
            if not file_descriptor:
                log.info("storage api download failed:")
                log.info("file doesn't exist")
                return
            app_iter = iter(partial(file_descriptor.read, BLOCK_SIZE), '')            
            return Response(
                app_iter=app_iter,
                content_type=self.raw_question["mimetype"],
                content_disposition="attachment; filename=" + self.raw_question["filename"].encode('utf-8'))   
        except storage.PersonValueError:
            log.info("storage api download failed:")
            log.info("peson argument cant be an empty string")
            return
        except DepartmentValueError:
            log.info("storage api download failed:")
            log.info("department argument cant be an empty string")
            return
        except QualifierValueError:
            log.info("storage api download failed:")
            log.info("qualifier argument cant be an empty string")
            return
        except BucketValueError:
            log.info("storage api download failed:")
            log.info("invalid bucket key argument")
            return
        except S3ValueError:
            log.info("storage api download failed:")
            log.info("invalid S3 credentials")
            return
        except SocketValueError:
            log.info("storage api download failed:")
            log.info("invalid host")
            return
       
    @XBlock.handler
    def download_solution(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Downloads the solution file from storage api and then returns a response
        """
        try:
            file_descriptor = storage.access_data(str(self.course_id), "solution", str(self.location.block_id))
            if not file_descriptor:
                log.info("storage api download failed:")
                log.info("file doesn't exist")
                return
            app_iter = iter(partial(file_descriptor.read, BLOCK_SIZE), '')
            return Response(
                app_iter=app_iter,
                content_type=self.raw_solution["mimetype"],
                content_disposition="attachment; filename=" + self.raw_solution["filename"].encode('utf-8'))
        except storage.PersonValueError:
            log.info("storage api download failed:")
            log.info("peson argument cant be an empty string")
            return
        except DepartmentValueError:
            log.info("storage api download failed:")
            log.info("department argument cant be an empty string")
            return
        except QualifierValueError:
            log.info("storage api download failed:")
            log.info("qualifier argument cant be an empty string")
            return
        except BucketValueError:
            log.info("storage api download failed:")
            log.info("invalid bucket key argument")
            return
        except S3ValueError:
            log.info("storage api download failed:")
            log.info("invalid S3 credentials")
            return
        except SocketValueError:
            log.info("storage api download failed:")
            log.info("invalid host")
            return

    def grade_this_guy(self):
        """
        Generates the path for the three files to be compared, passes them to the grader function, popuates the 
        score field, runtime.publish-es the grades so that it shows up in the progress page
        """
        answer = self._file_storage_path(self.raw_answer['sha1'], self.raw_answer['filename'])
        question = self._question_storage_path(self.raw_question['sha1'], self.raw_question['filename'])
        solution = self._solution_storage_path(self.raw_solution['sha1'], self.raw_solution['filename'])


        answer = os.path.join(IMAGEDIFF_ROOT, answer)
        question = os.path.join(IMAGEDIFF_ROOT, question)
        solution = os.path.join(IMAGEDIFF_ROOT, solution)

        self.score = grade(question, answer, solution)
        
        self.points=float(self.max_score())
        self.save()       
        self.runtime.publish(self, 'grade',{ 'value': self.score, 'max_value':self.max_score(),})
        self.save()
        return Response(json_body=self.student_state())

    def _file_storage_path(self, sha1, filename):
        """
        Returns the local path where the student's uploaded file is saved
        """
        # pylint: disable=no-member
        path = (
            '{loc.org}/{loc.course}/{loc.block_type}/{loc.block_id}/'
            '{student_id}/{sha1}{ext}'.format(
		student_id = self.xmodule_runtime.anonymous_student_id,
                loc=self.location,
                sha1=sha1,
                ext=os.path.splitext(filename)[1]
            )
        )
        return path

    def _question_storage_path(self, sha1, filename):
        """
        Returns the local path of the question file uploaded by the instructor
        """
        # pylint: disable=no-member
        path = (
            '{loc.org}/{loc.course}/{loc.block_type}/{loc.block_id}/'
            'static/question/{sha1}{ext}'.format(
                sha1 = sha1,
                loc=self.location,
                ext=os.path.splitext(filename)[1]
            )
        )
        return path

    def _solution_storage_path(self, sha1, filename):
        """
        Returns the local path of the solution file uploaded by the instructor
        """
        # pylint: disable=no-member
        path = (
            '{loc.org}/{loc.course}/{loc.block_type}/{loc.block_id}/'
            'static/solution/{sha1}{ext}'.format(
                sha1 = sha1,
                loc=self.location,
                ext=os.path.splitext(filename)[1]
            )
        )
        return path

def _get_sha1(file_descriptor):
    """
    Get file hex digest (fingerprint).
    """
    sha1 = hashlib.sha1()
    for block in iter(partial(file_descriptor.read, BLOCK_SIZE), ''):
        sha1.update(block)
    file_descriptor.seek(0)
    return sha1.hexdigest()

def _resource(path):  # pragma: NO COVER
    """
    Handy helper for getting resources from our kit.
    """
    data = pkg_resources.resource_string(__name__, path)
    return data.decode("utf8")

def load_resource(resource_path):  # pragma: NO COVER
    """
    Gets the content of a resource
    """
    resource_content = pkg_resources.resource_string(__name__, resource_path)
    return unicode(resource_content)

def render_template(template_path, context=None):  # pragma: NO COVER
    """
    Evaluate a template by resource path, applying the provided context.
    """
    if context is None:
        context = {}

    template_str = load_resource(template_path)
    template = Template(template_str)
    return template.render(Context(context))

def require(assertion):
    """
    Raises PermissionDenied if assertion is not true.
    """
    if not assertion:
        raise PermissionDenied

def workbench_scenario():
    return[
        ("ExcelSheetAssessmentXBlock", """agea"""), ]




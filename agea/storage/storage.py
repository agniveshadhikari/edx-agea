from boto.s3.key import Key
import os
import inspect
import hashlib
import MySQLdb as mdb
import sys
import wrapt
import boto
import shutil
import tempfile
from decorator import decorator as __decorator
from user_exceptions import *
from global_config import *
import logging
log = logging.getLogger(__name__)
sys.tracebacklimit = 0

# CONFIG

user = 'mysql root user'
passwd = 'password for root user'
db_name = 'database name as initialized in setup.py'
tbl_name = 'table name as initialized in setup.py'
AWS_ACCESS_KEY_ID = 'enter your access ID here'
AWS_ACCESS_KEY_SECRET = 'ener your Secret Key here'
host = 'enter your host here'
bucket_name = 'enter your bucket name here (should already be created)'
STORAGE_ROOT = '/edx/var/edxapp/media/'
FILE_STORE_TYPE = 'Unix'


curr_path = os.path.dirname(os.path.abspath(inspect.getfile(
             inspect.currentframe())))
os.chdir(curr_path)
f = open('global_config.py')
data = f.read().splitlines()
params = [d.split('=')[0].strip() for d in data]
f.close()


@wrapt.decorator
def inspect_signature(f, instance, args, kwargs):
    """This decorator checks for numbers of arguments passed to the function.
    """
    if inspect.getargspec(f)[3]:
        pos_args_count = (len(inspect.getargspec(f)[0]) -
                          len(inspect.getargspec(f)[3]))
    else:
        pos_args_count = len(inspect.getargspec(f)[0])
    pos_args_names = inspect.getargspec(f)[0][:pos_args_count]
    key_args_count = len(inspect.getargspec(f)[0]) - pos_args_count
    if kwargs:
        key_args_names = [key for key, value in kwargs.iteritems()]
    else:
        key_args_names = []
    if(len(args) < pos_args_count):
        diff = pos_args_count - len(args)
        for varname in pos_args_names[-diff:]:
            if varname not in key_args_names:
                raise TypeError('Argument {} is mandatory in function {}.'
                                .format(varname, f.__name__))
    return f(*args, **kwargs)


def __accepts(*types):
    """This decorator is for typechecking of function arguments."""
    def check_accepts(f):
        assert len(types) == f.func_code.co_argcount

        def new_f(f, *args, **kwds):
            args_name = inspect.getargspec(f)[0]
            args_values = inspect.getargspec(f)[3]
            fun_name = new_f.__name__
            for (a, t, name) in zip(args, types, args_name):
                if not isinstance(a, t) and a is not None:
                    raise TypeError(" in function %s arg %s should be of %s "
                                    "instead of %s"
                                    % (fun_name, name, t, type(a)))
            return f(*args, **kwds)
        new_f.func_name = f.func_name
        return __decorator(new_f)(f)
    return check_accepts


@inspect_signature
@__accepts(str, str)
def set_value(var_name, value):
    """Set the value of global parameter.

    Arguments:
        var_name(str): specifies the name of global parameter.
        value(str): specifies the value of global parameter.

    """
    global params
    if var_name not in params:
        raise GlobalValueError("trying to set unknown global config.")
    else:
        globals()[var_name] = value


def __get_value(var_name):
    """Returns the root directory for storage"""
    return globals()[var_name]


def __insert_key(department, person, qualifier, path, key):
    """Stores specified parameters into the table storage_key.

    Arguments:
        department(int): specifies the hash value of department to which the
                         storage unit belongs.
        person(int): specifies the hash value of person to which the storage
                        unit belongs.
        qualifier(int): specifies the hash value of the type of storage unit.
        path(str): specifies the path where file is stored.
        key(int): specifies the key from which storage can be accessed.
    """
    user = __get_value('user')
    passwd = __get_value('passwd')
    db_name = __get_value('db_name')
    tbl_name = __get_value('tbl_name')
    con = mdb.connect('localhost', user, passwd, db_name)
    cur = con.cursor()
    query = "INSERT INTO %s( \
            department, person, qualifier, complete_path, hash_key) \
            VALUES( '%s', '%s', '%s', '%s', %s)" \
            % (tbl_name, department, person, qualifier, path, key)
    try:
        cur.execute(query)
    except Exception as e:
        print e
    con.commit()
    con.close()


def __create_hash(path):
    """Creates digest of the string passed to the function which is used
       as hash value.

    Arguments:
        path(str): specifies the string whose hash_value needs to be generated.

    Returns:
        int: first 7 digits of the hash_value generated.
        """
    return (int(str(int(hashlib.md5(path).hexdigest(), 16))[:7]))


@inspect_signature
@__accepts(str, str, str, file)
def store_data(department, person, qualifier, content):
    """Store the content as a properly classified date and time stamped
       retrievable storage unit. It calls search keys method to check if there
       already exists a key with given arguments and (if yes) overwrites the
       existing file else a new key is created.

    Arguments:
        department(str): specifies the department to which the storage
                        unit belongs.
        person(str): specifies the person to which the storage unit belongs.
        qualifier(str): specifies the type of storage unit.
        content(file): points to the data stream from which the data is
                       retrieved and stored.

    Returns:
        int: a logical key which can be used to retrieve data directly
            without going through a search.

    Exceptions:
        DepartmentValueError: raised when department is an empty string.
        PersonValueError: raised when person is an empty string.
        QualifierValueError: raised when qualifier is an empty string.
        BucketValueError: raised when bucket is an empty string or specified
                           bucket does not exist.
        S3ValueError: raised when S3 credentials are incorrect.
        SocketValueError: raised when host parameter is incorrect.
    """
    log.info("---inside store_data in storage.py----------")
    log.info(boto.Version)
    if not department:
        raise DepartmentValueError("DepartmentValueError: department cannot"
                                   " be empty string.")
    if not person:
        raise PersonValueError("PersonValueError: person cannot be empty"
                               " string.")
    if not qualifier:
        raise QualifierValueError("QualifierValueError: qualifier cannot be"
                                  " empty string.")
    FILE_STORE_TYPE = __get_value('FILE_STORE_TYPE')
    flag =0
    if FILE_STORE_TYPE == 'Unix':
        key_from_table = search_keys(department, person, qualifier)
        flag = 0
        if not key_from_table:
            path = ''.join([department, "/", person, "/", qualifier])
            hash_value = __create_hash(path)
            STORAGE_ROOT = __get_value('STORAGE_ROOT')
            os.chdir(STORAGE_ROOT)
            if not os.path.exists(str(hash_value)):
                os.makedirs(str(hash_value))
            os.chdir(str(hash_value))
            temp = content.name
            if '/' in temp:
                parts = temp.split('/')
                flag = 1
            if(flag == 1):
                filename = parts[-1]
            else:
                filename = temp
            text = content.readlines()
            with open(filename, 'wb') as f:
                for line in text:
                    f.write(line)
            full_path = ''.join([str(hash_value), "/", filename])
            key = __create_hash(full_path)
            __insert_key(department, person, qualifier, full_path, key)
            return key
        else:
            user = __get_value('user')
            passwd = __get_value('passwd')
            db_name = __get_value('db_name')
            tbl_name = __get_value('tbl_name')
            con = mdb.connect('localhost', user, passwd, db_name)
            cur = con.cursor()
            query = "SELECT complete_path FROM %s \
                    WHERE hash_key = %s" % (tbl_name, key_from_table[0])
            cur.execute(query)
            result = cur.fetchall()
            path_from_table = [res[0] for res in result]
            STORAGE_ROOT = __get_value('STORAGE_ROOT')
            os.chdir(STORAGE_ROOT)
            text = content.readlines()
            with open(path_from_table[0], 'wb') as f:
                for line in text:
                    f.write(line)
            con.close()
            return key_from_table
    elif FILE_STORE_TYPE == "S3":
        if not AWS_ACCESS_KEY_ID and not AWS_ACCESS_KEY_SECRET:
            raise S3ValueError("S3ValueError: Credentials cannot be empty"
                               " string.")
        if not AWS_ACCESS_KEY_ID:
            raise S3ValueError("S3ValueError: Access Key Id cannot be empty"
                               " string.")
        if not AWS_ACCESS_KEY_SECRET:
            raise S3ValueError("S3ValueError: Access Key Secret cannot be"
                               " empty string")
        if not host:
            raise SocketValueError("SocketValueError: Host value cannot be"
                                   " empty string.")
        if not bucket_name:
            raise BucketValueError("BucketValueError: Bucket name cannot be"
                                   " empty string.")
        key_from_table = search_keys(department, person, qualifier)
        if not key_from_table:
            s3 = boto.connect_s3(AWS_ACCESS_KEY_ID, AWS_ACCESS_KEY_SECRET,
                                 host=host)
            try:
                log.info(bucket_name)
                log.info(s3.get_all_buckets())
                bucket = s3.get_bucket(bucket_name)
            except boto.exception.S3ResponseError as e:
                if e.code == 'AccessDenied':
                    raise S3ValueError("S3ValueError: Access denied as the"
                                       " credentials are incorrect.")
                if e.code == 'NoSuchBucket':
                    raise BucketValueError("BucketValueError: No Such Bucket"
                                           " exists.")
                log.info(e)
            except Exception as e:
                if e.errno == -2:
                    raise SocketValueError("SocketValueError: Check the value"
                                           " of host.")
                log.info(e)
            s3_key = Key(bucket)
            path = ''.join([department, "/", person, "/", qualifier])
            hash_value = __create_hash(path)
            temp = content.name
            if '/' in temp:
                parts = temp.split('/')
                flag = 1
            if(flag == 1):
                filename = parts[-1]
            else:
                filename = temp
            full_path = ''.join([str(hash_value), "/", filename])
            s3_key.key = full_path
            log.info('++++++if part++++++++++')
            log.info(content)
            log.info(full_path)
            log.info(s3_key)
            s3_key.set_contents_from_file(content)
            key = __create_hash(full_path)
            __insert_key(department, person, qualifier, full_path, key)
            return key
        else:
            user = __get_value('user')
            passwd = __get_value('passwd')
            db_name = __get_value('db_name')
            tbl_name = __get_value('tbl_name')
            con = mdb.connect('localhost', user, passwd, db_name)
            cur = con.cursor()
            query = "SELECT complete_path FROM %s WHERE \
                    hash_key = %s" % (tbl_name, key_from_table[0])
            cur.execute(query)
            result = cur.fetchall()
            path_from_table = [res[0] for res in result]
            s3 = boto.connect_s3(AWS_ACCESS_KEY_ID, AWS_ACCESS_KEY_SECRET,
                                 host=host)
            try:
                bucket = s3.get_bucket(bucket_name)
            except boto.exception.S3ResponseError as e:
                if e.code == 'AccessDenied':
                    raise S3ValueError("S3ValueError: Access denied as the"
                                       " credentials are incorrect.")
                if e.code == 'NoSuchBucket':
                    raise BucketValueError("BucketValueError: No Such Bucket"
                                           " exists.")
            except Exception as e:
                if e.errno == -2:
                    raise SocketValueError("SocketValueError: Check the value"
                                           " of host.")
            s3_key = bucket.get_key(path_from_table[0])
            log.info('++++++++++++++++')
            log.info(content)
            log.info(s3_key)
            s3_key.set_contents_from_file(content)
            con.close()
            return key_from_table
    else:
        print("Invalid Value for FILE STORE TYPE")


@inspect_signature
@__accepts(str, str, str)
def search_keys(department, person=None, qualifier=None):
    """Searches for key corresponding to the given arguments.

    Arguments:
        department(str): specifies the department to which the storage
                         unit belongs.
        person(str, optional): specifies the person to which the storage
                               unit belongs. Defaults to None.
        qualifier(str, optional): specifies the qualifier to which the
                                  storage unit belongs. Defaults to None.

    Returns:
        a list of keys(int) that matches the searching criteria,
        empty list is returned if no match found.

    Exceptions:
        DepartmentValueError: raised when department is an empty string.
        PersonValueError: raised when person is an empty string.
        QualifierValueError: raised when qualifier is an empty string.
    """
    if not department:
        raise DepartmentValueError("DepartmentValueError: department cannot"
                                   " be empty string.")
    if person is not None:
        if not person:
            raise PersonValueError("PersonValueError: person cannot be empty"
                                   " string.")
    if qualifier is not None:
        if not qualifier:
            raise QualifierValueError("QualifierValueError: qualifier cannot"
                                      " be empty string.")
    keys = []
    user = __get_value('user')
    passwd = __get_value('passwd')
    db_name = __get_value('db_name')
    tbl_name = __get_value('tbl_name')
    con = mdb.connect('localhost', user, passwd, db_name)
    cur = con.cursor()
    if department and person and qualifier:
        dep = department
        per = person
        qual = qualifier
        query = "SELECT hash_key FROM %s WHERE department = '%s'and \
          person = '%s' and qualifier = '%s'" % (tbl_name, dep, per, qual)
    elif department and qualifier:
        dep = department
        qual = qualifier
        query = "SELECT hash_key FROM %s WHERE department = '%s' \
             and qualifier = '%s'" % (tbl_name, dep, qual)
    elif department and person:
        dep = department
        per = person
        query = "SELECT hash_key FROM %s WHERE department = '%s' \
             and person = '%s'" % (tbl_name, dep, per)
    elif department:
        dep = department
        query = "SELECT hash_key FROM %s WHERE department = '%s'" \
                % (tbl_name, dep)
    cur.execute(query)
    result = cur.fetchall()
    if result:
        keys = [int(re[0]) for re in result]
    con.close()
    return keys


@inspect_signature
@__accepts(int)
def get_owner(key):
    """Searches for department, person and qualifier correspnding to the key.
    Arguments:
        key(int): specifies the logical key for retrieving the storage unit.

    Returns:
        department, person and qualifier as list.

    Exceptions:
        KeyValueError: where no corresponding values for the specified key.

    """
    user = __get_value('user')
    passwd = __get_value('passwd')
    db_name = __get_value('db_name')
    tbl_name = __get_value('tbl_name')
    con = mdb.connect('localhost', user, passwd, db_name)
    cur = con.cursor()
    query = "SELECT department, person, qualifier FROM %s WHERE \
            hash_key = %s" % (tbl_name, key)
    cur.execute(query)
    result = cur.fetchall()
    if result:
        for re in result:
            owner = list(re)
    else:
        raise KeyValueError("KeyValueError: No corresponding values for the"
                            " specified key.")
    con.close()
    return owner


@inspect_signature
@__accepts(str, str, str)
def access_data(department, person, qualifier):
    """Searches for the file corresponding to the specified arguments.

     Arguments:
        department(str): specifies the department to which the storage
                        unit belongs.
        person(str): specifies the person to which the storage unit belongs.
        qualifier(str): specifies the type of storage unit.

    Returns:
        pointer to the file from where data can be retrieved.

    Exceptions:
        DepartmentValueError: raised when department is an empty string.
        PersonValueError: raised when person is an empty string.
        QualifierValueError: raised when qualifier is an empty string.
        BucketValueError: raised when bucket is an empty string or specified
                           bucket does not exist.
        S3ValueError: raised when S3 credentials are incorrect.
        SocketValueError: raised when host parameter is incorrect.
    """
    if not department:
        raise DepartmentValueError("DepartmentValueError: department cannot"
                                   " be empty string.")
    if not person:
        raise PersonValueError("PersonValueError: person cannot be empty"
                               " string.")
    if not qualifier:
        raise QualifierValueError("QualifierValueError: qualifier cannot be"
                                  " empty string.")
    dep = department
    per = person
    qual = qualifier
    user = __get_value('user')
    passwd = __get_value('passwd')
    db_name = __get_value('db_name')
    tbl_name = __get_value('tbl_name')
    con = mdb.connect('localhost', user, passwd, db_name)
    cur = con.cursor()
    query = "SELECT complete_path FROM %s WHERE department = '%s' and \
             person = '%s' and qualifier = '%s'" % (tbl_name, dep, per, qual)
    cur.execute(query)
    result = cur.fetchall()
    log.info('-----path-----')
    log.info(result)
    if not result:
        print "Record Not Found"
    else:
        path = [re[0] for re in result]
        FILE_STORE_TYPE = __get_value('FILE_STORE_TYPE')
        if FILE_STORE_TYPE == 'Unix':
            STORAGE_ROOT = __get_value('STORAGE_ROOT')
            os.chdir(STORAGE_ROOT)
            fp = open(path[0], 'rb')
            return fp
        elif FILE_STORE_TYPE == 'S3':
            if not AWS_ACCESS_KEY_ID and not AWS_ACCESS_KEY_SECRET:
                raise S3ValueError("S3ValueError: Credentials cannot be empty"
                                   " string.")
            if not AWS_ACCESS_KEY_ID:
                raise S3ValueError("S3ValueError: Access Key Id cannot be"
                                   " empty string.")
            if not AWS_ACCESS_KEY_SECRET:
                raise S3ValueError("S3ValueError: Access Key Secret cannot be"
                                   " empty string")
            if not host:
                raise SocketValueError("SocketValueError: Host value cannot"
                                       " be empty string.")
            if not bucket_name:
                raise BucketValueError("BucketValueError: The bucket name "
                                       "cannot be empty string.")
            s3 = boto.connect_s3(AWS_ACCESS_KEY_ID,
                                 AWS_ACCESS_KEY_SECRET, host=host)
            try:
                bucket = s3.get_bucket(bucket_name)
            except boto.exception.S3ResponseError as e:
                if e.code == 'AccessDenied':
                    raise S3ValueError("S3ValueError: Access denied as the"
                                       " credentials are incorrect.")
                if e.code == 'NoSuchBucket':
                    raise BucketValueError("BucketValueError: No Such"
                                           " Bucket exists.")
            except Exception as e:
                if e.errno == -2:
                    raise SocketValueError("SocketValueError: Check the value"
                                           " of host.")
            s3_key = bucket.get_key(path[0])
            fp = tempfile.NamedTemporaryFile(delete=True)
            s3_key.get_contents_to_filename(fp.name)
            f = open(fp.name, 'rb')
            return f
        else:
            print("Invalid Value for FILE STORE TYPE")
    con.close()


@inspect_signature
@__accepts(str, str, str)
def remove_data(department, person=None, qualifier=None):
    """Removes the latest content in a particular order.
       If all parameters are specified then the latest storage unit from
       department, matching the person and qualifier
       with its corresponding key is removed.
       If qualifier is not specified then all of the latest storage units
       from department matching the person with their corresponding keys are
       removed.
       If person is not specified then all of the latest storage units from
       the department, matching the qualifier with their corresponding keys
       are removed.
       If only department is specified then all of the latest storage units
       from the department with their corresponding keys are removed.

    Arguments:
        department(str): specifies the department to which the storage unit
                         belongs.
        person(str, optional): specifies the person to which the storage unit
                               belongs. Default value is None.
        qualifier(str, optional): specifies the qualifier to which the storage
                                  unit belongs. Default value is None.

    Exceptions:
        DepartmentValueError: raised when department is an empty string.
        PersonValueError: raised when person is an empty string.
        QualifierValueError: raised when qualifier is an empty string.
    """
    if not department:
        raise DepartmentValueError("DepartmentValueError: department cannot"
                                   " be empty string.")
    if person is not None:
        if not person:
            raise PersonValueError("PersonValueError: person cannot be empty"
                                   " string.")
    if qualifier is not None:
        if not qualifier:
            raise QualifierValueError("QualifierValueError: qualifier cannot"
                                      " be empty string.")
    user = __get_value('user')
    passwd = __get_value('passwd')
    db_name = __get_value('db_name')
    tbl_name = __get_value('tbl_name')
    con = mdb.connect('localhost', user, passwd, db_name)
    cur = con.cursor()
    if department and person and qualifier:
        dep = department
        per = person
        qual = qualifier
        query = "DELETE FROM %s WHERE department = '%s' and person = '%s' \
                 and qualifier = '%s'" % (tbl_name, dep, per, qual)
        query1 = "SELECT * FROM %s WHERE department = '%s' and person = '%s' \
                 and qualifier = '%s'" % (tbl_name, dep, per, qual)
    elif department and person:
        dep = department
        per = person
        query = "DELETE FROM %s WHERE department = '%s' and \
                person = '%s'" % (tbl_name, dep, per)
        query1 = "SELECT * FROM %s WHERE department = '%s' and \
                person = '%s'" % (tbl_name, dep, per)
    elif department and qualifier:
        dep = department
        qual = qualifier
        query = "DELETE FROM %s WHERE department = '%s' and \
                 qualifier = '%s'" % (tbl_name, dep, qual)
        query1 = "SELECT * FROM %s WHERE department = '%s' and \
                   qualifier = '%s'" % (tbl_name, dep, qual)
    elif department:
        dep = department
        query = "DELETE FROM %s WHERE department = '%s'" % (tbl_name, dep)
        query1 = "SELECT * FROM %s WHERE department = '%s'" % (tbl_name, dep)
    cur.execute(query1)
    result = cur.fetchall()
    if not result:
        print "No Record Found"
    else:
        cur.execute(query)
        con.commit()
    con.close()


@inspect_signature
@__accepts(str, str, str, str, str, str)
def copy_data(department_source, department_destination, person_source=None,
              person_destination=None, qualifier_source=None,
              qualifier_destination=None):
    """Copies the latest storage unit in particular order.
       If all parameters are specified then the latest storage unit from
       department_source, matching the person_source and qualifier_source
       is copied.
       If qualifier_source and qualifier_destination are not specified then
       all of the latest storage units from department_source, matching the
       person_source are copied.
       If person_source and person_destnation are not specified then all of
       the latest storage unit from the department_source, matching the
       qualifier_source are copied.
       If only department_source and department_destination are specified then
       all of the latest storage units from the department_source are copied.

    Arguments:
        department_source(str): specifies the department to which the storage
                                unit belongs.
        department_destination(str): specifies the department to which the
                                     storage unit belongs.
        person_source(str, optional): specifies the person to which the storage
                                      unit belongs. Defaults to None.
        person_destination(str, optional): specifies the person to which
                                           storage unit belongs. Defaults
                                           to None.
        qualifier_source(str, optional): specifies the qualifier to which
                                         storage unit belongs. Defaults
                                         to None.
        qualifier_destination(str, optional): specifies the qualifier to which
                                              storage unit belongs. Defaults
                                              to None.

    Returns:
        keys corresponding to storage unit which are copied.

    Exceptions:
        DepartmentValueError: raised when department is an empty string.
        PersonValueError: raised when person is an empty string.
        QualifierValueError: raised when qualifier is an empty string.
        BucketValueError: raised when bucket is an empty string or specified
                           bucket does not exist.
        S3ValueError: raised when S3 credentials are incorrect.
        SocketValueError: raised when host parameter is incorrect.
    """
    if not department_source:
        raise DepartmentValueError("DepartmentValueError: department_source"
                                   " cannot be empty string.")
    if not department_destination:
        raise DepartmentValueError("DepartmentValueError: "
                                   "department_destination cannot be empty"
                                   " string.")
    if person_source is not None and person_destination is not None:
        if not person_source:
            raise PersonValueError("PersonValueError: person_source cannot"
                                   " be empty string.")
        if not person_destination:
            raise PersonValueError("PersonValueError: person_destination"
                                   " cannot be empty string.")
    if person_source is not None and person_destination is None:
        if not person_source:
            raise PersonValueError("PersonValueError: person_source cannot"
                                   " be empty string.")
    if person_destination is not None and person_source is None:
        if not person_destination:
            raise PersonValueError("PersonValueError: person_destination "
                                   "cannot be empty string.")
    if (person_source and not person_destination or
            person_destination and not person_source):
        raise PersonValueError("PersonValueError: If provided then both "
                               "person_source & person_destination "
                               "should be provided.")
    if qualifier_source is not None and qualifier_destination is not None:
        if not qualifier_source:
            raise QualifierValueError("QualifierValueError: qualifier_source"
                                      " cannot be empty string.")
        if not qualifier_destination:
            raise QualifierValueError("QualifierValueError: qualifier"
                                      "destination cannot be empty string.")
    if qualifier_source is not None and qualifier_destination is None:
        if not qualifier_source:
            raise QualifierValueError("QualifierValueError: qualifier_source"
                                      " cannot be empty string.")
    if qualifier_destination is not None and qualifier_source is None:
        if not qualifier_destination:
            raise QualifierValueError("QualifierValueError: qualifier_"
                                      "destination cannot be empty string.")
    if (qualifier_source and not qualifier_destination or
            qualifier_destination and not qualifier_source):
        raise QualifierValueError("QualifierValueError: If provided then both"
                                  " qualifier_source & qualifier_destination"
                                  " should be provided.")
    keys = []
    user = __get_value('user')
    passwd = __get_value('passwd')
    db_name = __get_value('db_name')
    tbl_name = __get_value('tbl_name')
    con = mdb.connect('localhost', user, passwd, db_name)
    cur = con.cursor()
    if (department_source and department_destination and person_source and
       person_destination and qualifier_source and qualifier_destination):
        dep_s = department_source
        per_s = person_source
        qual_s = qualifier_source
        query = "SELECT complete_path from %s where department = '%s'and \
        person = '%s' and qualifier = '%s'" % (tbl_name, dep_s, per_s, qual_s)
        cur.execute(query)
        result = cur.fetchall()
        if not result:
            print "Record Not Found"
        else:
            source_path = [res[0] for res in result]
            dep_d = department_destination
            per_d = person_destination
            qual_d = qualifier_destination
            destination_path = ''.join([dep_d, "/", per_d, "/", qual_d])
            hash_value_destination = __create_hash(destination_path)
            if FILE_STORE_TYPE == 'Unix':
                STORAGE_ROOT = __get_value('STORAGE_ROOT')
                os.chdir(STORAGE_ROOT)
                if not os.path.exists(str(hash_value_destination)):
                    os.makedirs(str(hash_value_destination))
                shutil.copy(source_path[0], str(hash_value_destination))
                os.chdir(str(hash_value_destination))
                filename = os.listdir(os.getcwd())[0]
                full_path = ''.join([str(hash_value_destination), "/",
                                    filename])
                key = __create_hash(full_path)
                keys.append(key)
                __insert_key(dep_d, per_d, qual_d, full_path, key)
            elif FILE_STORE_TYPE == 'S3':
                if not AWS_ACCESS_KEY_ID and not AWS_ACCESS_KEY_SECRET:
                    raise S3ValueError("S3ValueError: Credentials cannot be"
                                       " empty string.")
                if not AWS_ACCESS_KEY_ID:
                    raise S3ValueError("S3ValueError: Access Key Id cannot"
                                       " be empty string.")
                if not AWS_ACCESS_KEY_SECRET:
                    raise S3ValueError("S3ValueError: Access Key Secret"
                                       " cannot be empty string")
                if not host:
                    raise SocketValueError("SocketValueError: Host value"
                                           " cannot be empty string.")
                if not bucket_name:
                    raise BucketValueError("BucketValueError: The bucket name"
                                           " cannot be empty string.")
                s3 = boto.connect_s3(AWS_ACCESS_KEY_ID,
                                     AWS_ACCESS_KEY_SECRET, host=host)
                try:
                    bucket = s3.get_bucket(bucket_name)
                except boto.exception.S3ResponseError as e:
                    if e.code == 'AccessDenied':
                        raise S3ValueError("S3ValueError: Access denied as"
                                           " the credentials are incorrect.")
                    if e.code == 'NoSuchBucket':
                        raise BucketValueError("BucketValueError:No Such"
                                               " Bucket exists.")
                except Exception as e:
                    if e.errno == -2:
                        raise SocketValueError("SocketValueError: Check the"
                                               " value of host.")
                old_key = bucket.get_key(source_path[0])
                old_key_name = source_path[0].split("/")[-1]
                ftemp = tempfile.NamedTemporaryFile(delete=True)
                old_key.get_contents_to_filename(ftemp.name)
                full_path = ''.join([str(hash_value_destination), "/",
                                    old_key_name])
                fp = open(ftemp.name, 'rb')
                new_key = Key(bucket)
                new_key.key = full_path
                new_key.set_contents_from_file(fp)
                fp.close()
                key = __create_hash(full_path)
                keys.append(key)
                __insert_key(dep_d, per_d, qual_d, full_path, key)
            else:
                print("Invalid Value for FILE STORE TYPE")
    elif (department_source and department_destination and
          qualifier_source and qualifier_destination):
        path_s = []
        person_s = []
        dep_s = department_source
        qual_s = qualifier_source
        query = "SELECT person, complete_path FROM %s WHERE department = '%s' \
                 and qualifier = '%s'" % (tbl_name, dep_s, qual_s)
        cur.execute(query)
        result = cur.fetchall()
        if not result:
            print "Record Not Found"
        else:
            for re in result:
                person_s.append(re[0])
                path_s.append(re[1])
            dep_d = department_destination
            qual_d = qualifier_destination
            for index in range(len(path_s)):
                destination_path = ''.join([str(dep_d), "/",
                                           str(person_s[index]), "/",
                                           str(qual_d)])
                hash_value_destination = __create_hash(destination_path)
                if FILE_STORE_TYPE == 'Unix':
                    STORAGE_ROOT = __get_value('STORAGE_ROOT')
                    os.chdir(STORAGE_ROOT)
                    if not os.path.exists(str(hash_value_destination)):
                        os.makedirs(str(hash_value_destination))
                    shutil.copy(path_s[index], str(hash_value_destination))
                    os.chdir(str(hash_value_destination))
                    filename = os.listdir(os.getcwd())[0]
                    full_path = ''.join([str(hash_value_destination), "/",
                                        filename])
                    key = __create_hash(full_path)
                    keys.append(key)
                    __insert_key(dep_d, person_s[index], qual_d, full_path,
                                 key)
                elif FILE_STORE_TYPE == 'S3':
                    if not AWS_ACCESS_KEY_ID and not AWS_ACCESS_KEY_SECRET:
                        raise S3ValueError("S3ValueError: Credentials cannot"
                                           " be empty string.")
                    if not AWS_ACCESS_KEY_ID:
                        raise S3ValueError("S3ValueError: Access Key Id"
                                           " cannot be empty string.")
                    if not AWS_ACCESS_KEY_SECRET:
                        raise S3ValueError("S3ValueError: Access Key Secret"
                                           " cannot be empty string")
                    if not host:
                        raise SocketValueError("SocketValueError: Host value"
                                               " cannot be empty string.")
                    if not bucket_name:
                        raise BucketValueError("BucketValueError: The bucket "
                                               "name cannot be empty string.")
                    s3 = boto.connect_s3(AWS_ACCESS_KEY_ID,
                                         AWS_ACCESS_KEY_SECRET, host=host)
                    try:
                        bucket = s3.get_bucket(bucket_name)
                    except boto.exception.S3ResponseError as e:
                        if e.code == 'AccessDenied':
                            raise S3ValueError("S3ValueError:Access denied as"
                                               " credentials are"
                                               " incorrect.")
                        if e.code == 'NoSuchBucket':
                            raise BucketValueError("BucketValueError: No Such"
                                                   " Bucket exists.")
                    except Exception as e:
                        if e.errno == -2:
                            raise SocketValueError("SocketValueError: Check"
                                                   " the value of host.")
                    old_key = bucket.get_key(path_s[index])
                    old_key_name = path_s[index].split("/")[-1]
                    ftemp = tempfile.NamedTemporaryFile(delete=True)
                    old_key.get_contents_to_filename(ftemp.name)
                    full_path = ''.join([str(hash_value_destination), "/",
                                        old_key_name])
                    fp = open(ftemp.name, 'rb')
                    new_key = Key(bucket)
                    new_key.key = full_path
                    new_key.set_contents_from_file(fp)
                    fp.close()
                    key = __create_hash(full_path)
                    keys.append(key)
                    __insert_key(dep_d, person_s[index], qual_d, full_path,
                                 key)
                else:
                    print("Invalid Value for FILE STORE TYPE")
    elif (department_source and department_destination and person_source and
          person_destination):
        path_s = []
        qualifier_s = []
        dep_s = department_source
        per_s = person_source
        query = "SELECT qualifier, complete_path from %s where \
            department = '%s' and person = '%s'" % (tbl_name, dep_s, per_s)
        cur.execute(query)
        result = cur.fetchall()
        if not result:
            print "Result Not Found"
        else:
            for re in result:
                qualifier_s.append(re[0])
                path_s.append(re[1])
            dep_d = department_destination
            per_d = person_destination
            for index in range(len(path_s)):
                destination_path = ''.join([str(dep_d), "/", str(per_d), "/",
                                           str(qualifier_s[index])])
                hash_value_destination = __create_hash(destination_path)
                if FILE_STORE_TYPE == 'Unix':
                    STORAGE_ROOT = __get_value('STORAGE_ROOT')
                    os.chdir(STORAGE_ROOT)
                    if not os.path.exists(str(hash_value_destination)):
                        os.makedirs(str(hash_value_destination))
                    shutil.copy(path_s[index], str(hash_value_destination))
                    os.chdir(str(hash_value_destination))
                    filename = os.listdir(os.getcwd())[0]
                    full_path = ''.join([str(hash_value_destination), "/",
                                        filename])
                    key = __create_hash(full_path)
                    keys.append(key)
                    __insert_key(dep_d, per_d, qualifier_s[index], full_path,
                                 key)
                elif FILE_STORE_TYPE == 'S3':
                    if not AWS_ACCESS_KEY_ID and not AWS_ACCESS_KEY_SECRET:
                        raise S3ValueError("S3ValueError: Credentials cannot"
                                           " be empty string.")
                    if not AWS_ACCESS_KEY_ID:
                        raise S3ValueError("S3ValueError: Access Key Id cannot"
                                           " be empty string.")
                    if not AWS_ACCESS_KEY_SECRET:
                        raise S3ValueError("S3ValueError: Access Key Secret"
                                           " cannot be empty string")
                    if not host:
                        raise SocketValueError("SocketValueError: Host value"
                                               " cannot be empty string.")
                    if not bucket_name:
                        raise BucketValueError("BucketValueError: The bucket "
                                               "name cannot be empty string.")
                    s3 = boto.connect_s3(AWS_ACCESS_KEY_ID,
                                         AWS_ACCESS_KEY_SECRET, host=host)
                    try:
                        bucket = s3.get_bucket(bucket_name)
                    except boto.exception.S3ResponseError as e:
                        if e.code == 'AccessDenied':
                            raise S3ValueError("S3ValueError: Access denied"
                                               " as the credentials are"
                                               " incorrect.")
                        if e.code == 'NoSuchBucket':
                            raise BucketValueError("BucketValueError: No Such"
                                                   " Bucket exists.")
                    except Exception as e:
                        if e.errno == -2:
                            raise SocketValueError("SocketValueError: Check"
                                                   " the value of host.")
                    old_key = bucket.get_key(path_s[index])
                    old_key_name = path_s[index].split("/")[-1]
                    ftemp = tempfile.NamedTemporaryFile(delete=True)
                    old_key.get_contents_to_filename(ftemp.name)
                    full_path = ''.join([str(hash_value_destination), "/",
                                        old_key_name])
                    fp = open(ftemp.name, 'rb')
                    new_key = Key(bucket)
                    new_key.key = full_path
                    new_key.set_contents_from_file(fp)
                    fp.close()
                    key = __create_hash(full_path)
                    keys.append(key)
                    __insert_key(dep_d, per_d, qualifier_s[index], full_path,
                                 key)
                else:
                    print("Invalid Value for FILE STORE TYPE")
    elif (department_source and department_destination):
        path_s = []
        person_s = []
        qualifier_s = []
        dep_s = department_source
        query = "SELECT person, qualifier, complete_path from %s \
               WHERE department = '%s'" % (tbl_name, dep_s)
        cur.execute(query)
        result = cur.fetchall()
        if not result:
            print "Result Not Found"
        else:
            for re in result:
                person_s.append(re[0])
                qualifier_s.append(re[1])
                path_s.append(re[2])
            dep_d = department_destination
            for index in range(len(path_s)):
                destination_path = ''.join([str(dep_d), "/",
                                           str(person_s[index]), "/",
                                           str(qualifier_s[index])])
                hash_value_destination = __create_hash(destination_path)
                if FILE_STORE_TYPE == 'Unix':
                    STORAGE_ROOT = __get_value('STORAGE_ROOT')
                    os.chdir(STORAGE_ROOT)
                    if not os.path.exists(str(hash_value_destination)):
                        os.makedirs(str(hash_value_destination))
                    shutil.copy(path_s[index], str(hash_value_destination))
                    os.chdir(str(hash_value_destination))
                    filename = os.listdir(os.getcwd())[0]
                    full_path = ''.join([str(hash_value_destination), "/",
                                        filename])
                    key = __create_hash(full_path)
                    keys.append(key)
                    __insert_key(dep_d, person_s[index], qualifier_s[index],
                                 full_path, key)
                elif FILE_STORE_TYPE == 'S3':
                    if not AWS_ACCESS_KEY_ID and not AWS_ACCESS_KEY_SECRET:
                        raise S3ValueError("S3ValueError: Credentials cannot"
                                           " be empty string.")
                    if not AWS_ACCESS_KEY_ID:
                        raise S3ValueError("S3ValueError:Access Key Id cannot"
                                           " be empty string.")
                    if not AWS_ACCESS_KEY_SECRET:
                        raise S3ValueError("S3ValueError: Access Key Secret"
                                           " cannot be empty string")
                    if not host:
                        raise SocketValueError("SocketValueError: Host value"
                                               " cannot be empty string.")
                    if not bucket_name:
                        raise BucketValueError("BucketValueError: The bucket "
                                               "name cannot be empty string.")
                    s3 = boto.connect_s3(AWS_ACCESS_KEY_ID,
                                         AWS_ACCESS_KEY_SECRET, host=host)
                    try:
                        bucket = s3.get_bucket(bucket_name)
                    except boto.exception.S3ResponseError as e:
                        if e.code == 'AccessDenied':
                            raise S3ValueError("S3ValueError:Access Denied as"
                                               " the credentials are"
                                               " incorrect.")
                        if e.code == 'NoSuchBucket':
                            raise BucketValueError("BucketValueError: No Such"
                                                   " Bucket exists.")
                    except Exception as e:
                        if e.errno == -2:
                            raise SocketValueError("SocketValueError: Check"
                                                   " the value of host.")
                    old_key = bucket.get_key(path_s[index])
                    old_key_name = path_s[index].split("/")[-1]
                    ftemp = tempfile.NamedTemporaryFile(delete=True)
                    old_key.get_contents_to_filename(ftemp.name)
                    full_path = ''.join([str(hash_value_destination), "/",
                                        old_key_name])
                    fp = open(ftemp.name, 'rb')
                    new_key = Key(bucket)
                    new_key.key = full_path
                    new_key.set_contents_from_file(fp)
                    fp.close()
                    key = __create_hash(full_path)
                    keys.append(key)
                    __insert_key(dep_d, person_s[index], qualifier_s[index],
                                 full_path, key)
                else:
                    print("Invalid Value for FILE STORE TYPE")
    con.close()
    return keys

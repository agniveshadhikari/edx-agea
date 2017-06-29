**************
 Storage Unit
**************

Installation
------------

The package can be obtained from GIT either as:
  
    # git clone https://<gitlab.se.iitb.ac.in>/<filename>

or can be downloaded as tar file. Then do:

    # tar -xvf <filename>.tar 

To install this package navigate to the *setup.py* file in *storage_package* directory, run::

    # python setup.py install

and give the details as asked.

Usage
-----
Before you start using the library, you are required to set the values of following global parameters::

    user
    passwd
    db_name
    tbl_name
    STORAGE_ROOT
    FILE_STORE_TYPE
    AWS_ACCESS_KEY_SECRET
    AWS_ACCESS_KEY_ID
    host
    

Use function call set_value as::

    # set_value('var_name', 'value')

where `var_name` is the name of global parameter and `value` is the value of global parameter.

Note: The values for global paramters `user`, `passwd`, `db_name` and `tbl_name` should be the same as given during installation time.


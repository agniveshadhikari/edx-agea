from setuptools import setup
from setuptools.command.install import install
import MySQLdb as mdb

class CustomInstallCommand(install):
    """Customized setuptools install command - prints a friendly greeting."""
    def run(self):
        print "---------- Creating Database and Table------------"
        user  = raw_input("enter user name for mysql database: ")
        passwd  = raw_input("enter password for mysql database: ")
        db_name = raw_input("enter database name: ")
        tbl_name = raw_input("enter table name: ")
        con = mdb.connect('localhost', user , passwd)
        cur = con.cursor()
   
        query = "create database %s" % db_name
        cur.execute(query)
        print "------------------Database Created----------------"
        query = "use %s" % db_name
        cur.execute(query)

        query = "create table %s ( \
                  department varchar(30) NOT NULL, \
                  person varchar(30) NOT NULL, \
                  qualifier varchar(30) NOT NULL, \
                  complete_path varchar(30) NOT NULL, \
                  hash_key bigint NOT NULL UNIQUE \
                  )" % tbl_name

        cur.execute(query)
        print "---------------Table Created-------------------"
        con.close()
        install.run(self)


setup(name='storage',
       version = '0.1',
       cmdclass={
        'install': CustomInstallCommand,
       },
      )

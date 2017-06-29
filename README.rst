Auto Graded Excel Assignment XBlock
===================================

This package provides an XBlock for use with the edX platform which
provides an excel sheet assessment. Students are given question/template files and 
are invited to upload their solutions. The uploaded solutions are automatically 
compaerd to the files uploaded by the teacher and assigned a grade.



Installation
------------

Dependency
~~~~~~~~~~

This module depends on the package ``openpyxl`` to be installed in the environment.
If this is already available, skip to the next section (Production Installation).

	1. Run the commands 


Production Installation 
~~~~~~~~~~~~~~~~~~~~~~~

Create a branch of edx-platform to commit a few minor changes:

	1. Copy the ``agea`` directory to ``/home/edx``

	2. Run the command
		.. code:: sh

		"sudo -u edxapp /edx/bin/pip.edxapp install /home/edx/edx-agea"

		Verify that in ``/edx/app/edxapp/venvs/edxapp/lib/python2.7/site-packages/`` 
		a directory ``agea`` has now been created. If not, the installation has 
		not been successful.

	3. Add agea to installed Django apps

		- In ``/edx/app/edxapp/edx-platform/cms/envs/common.py``, add ``'agea'``
		to ``INSTALLED_APPS``

		- In ``/edx/app/edxapp/edx-platform/lms/envs/common.py``, add ``'agea'``
		to ``INSTALLED_APPS``

	4. Configure file storage

		1. Run command

			.. code:: sh

			"python /edx/app/edxapp/venvs/edxapp/lib/python2.7/site-packages/agea/storage_setup/setup.py"


		2. The following information is required to be entered at the prompts:

			- The mysql root username
			- The mysql root password
			- The mysql database name where you want the file storage backend to reside
			- The mysql table name where you want the file storage backend to reside


		3. Open ``/edx/app/edxapp/venvs/edxapp/lib/python2.7/site-packages/agea/storage/storage.py``, and enter the details in the section marked Credentials

			- ``user`` The mysql root username
			- ``passwd``: The mysql root password
			- ``db_name``: The mysql database name
			- ``tbl_name``: The mysql table name
			- ``STORAGE_ROOT``: The local storage root directory
			- ``FILE_STORE_TYPE``: ``unix`` for local storage or ``S3`` for AWS
			- ``AWS_ACCESS_KEY_SECRET``: The AWS secret access key
			- ``AWS_ACCESS_KEY_ID``: The AWS ID
			- ``host``: The AWS host IP



Course Authoring in edX Studio
------------------------------

1. Change Advanced Settings

	1. Open a course you are authoring and select "Settings" ⇒ "Advanced
	Settings

	2. Navigate to the section titled "Advanced Module List"

	3. Add ``"agea"`` to module list

	4. Click save, and studio should save your changes

		.. figure:: https://raw.githubusercontent.com/mitodl/edx-sga/screenshots/img/screenshot-studio-advanced-settings.png
			:alt: the Advanced Module List section in Advanced Settings

2. Create an AGEA XBlock

	1. Return to the Course Outline

	2. Create a Section, Sub-section and Unit, if you haven't already

	3. In the "Add New Component" interface, you should now see an "Advanced" 
		button

	4. Click "Advanced" and choose "Excel Autograded Assignment"

		.. figure:: https://raw.githubusercontent.com/mitodl/edx-sga/screenshots/img/screenshot-studio-new-unit.png
			:alt: buttons for problems types, including advanced types


3. Settings

	- Question Parameters:

		- Question title: This should be a short title to the question, and not the question statement itself. This
			text appears at various places such as the title of the tab or browser, or in the navigation pane. Recommended
			max length is 140 characters.

		- Question text: This text is the actual question. This can be elaborate, and there is no limit on the maximum length.
			Recommended max length is 500 characters. If the required question statement exceeds this limit, it is recommended
			that the question statement is included in the question file that is to be uploaded, and a shorter question text be
			put in this field.

		- Maximum score: This field requres you to enter the score you want students to be graded out of. This need not be the 
			maximum attainable score. The students will be assigned grade for this problem as a percentage out of this value.
			For example, if the maximum attainable score is 25 but you want any score above 20 to be given full credit (100% credit)
			for this problem, you enter the value 20 in this field. This value has to be an integer.

		- Problem Weight: This is the weightage of this problem in this assessment type. The sum of weightages of all
			problems in a particular assessment must be equal to 1. If you are unsure, we recommend you have this value as 1.0.
			This field accepts decimal values.

		- Maximum attempts permitted: This value corresponds to the maximum number of submission a student is allowed to make
			for this problem. Leave this value blank if you don't want to limit the number of submissions. Enter positive values
			only.

	- Question File Upload:

		- Click on the "Select file" button to choose the file you want to upload as your question from your computer.

		- In the pop-up box, navigate to the folder, select the file you want to upload, and click "Open"

		- The selected filename apppears on the button now. Click the button to upload the file.


	- Solution File Upload:

		- Click on the "Select file" button to choose the file you want to upload as your solution from your computer.

		- In the pop-up box, navigate to the folder, select the file you want to upload, and click "Open"

		- The selected filename apppears on the button now. Click the button to upload the file.



	.. figure:: https://raw.githubusercontent.com/mitodl/edx-sga/screenshots/img/screenshot-studio-editing-sga.png
	:alt: Editing SGA Settings

4. Grading Policy

SGA XBlocks inherit grading settings just like any other problem type. You 
can include them in homework, exams or any assignment type of your choosing.
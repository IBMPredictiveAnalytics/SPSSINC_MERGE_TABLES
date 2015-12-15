This package contains the SPSSINC MERGE TABLES extension command.  It merges one table into another.

SPSSINC MERGE TABLES was originally written for the purpose of merging the test statistics table from CTABLES into the main table, but it has many other uses.  For simple problems, no Python programming is required.  Complex tables may require writing small Python functions to specify how the rows and columns of the two tables are matched up.



The package includes a dialog box interface.

This command cannot vertically align the labels in SPSS Statistics 17.0.0 or 17.0.1.


Executing
command name /HELP
will display the full syntax.  There are details in the .py file on writing custom merging functions.

To install these commands, which require at least SPSS Statistics 17 and the Python Programmability Plug-In, 
1. save the files into the extension subdirectory of your SPSS Statistics installation.  
2. Use Utilities>Install Custom Dialog to install the dialog interface and then restart SPSS Statistics.



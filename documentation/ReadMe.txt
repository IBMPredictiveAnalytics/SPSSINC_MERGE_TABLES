This package contains two extension commands:
SPSSINC MERGE TABLES - merge one pivot table into another, and
SPSSINC CENSOR TABLES - censor certain cells of a pivot table based on the values of a test statistic.

SPSSINC MERGE TABLES is an extension command implemented in Python for merging the contents of one table into another.  It was originally written for the purpose of merging the test statistics table from CTABLES into the main table, but it has many other uses.  For simple problems, no Python programming is required.  Complex tables may require writing small Python functions to specify how the rows and columns of the two tables are matched up.



The package now includes a dialog box interface.

This command cannot vertically align the labels in SPSS Statistics 17.0.0 or 17.0.1.  This is expected to work when 17.0.2 is released.

SPSSINC CENSOR TABLES is an extension command for blanking or otherwise obscuring specified cells in a pivot table based on the values of statistics in related cells.  It includes a dialog box interface that will appear on the Utilities menu.

For both commands, executing
command name /HELP
will display the full syntax.  There are details in the tables17.py file on writing custom merging functions.

To install these commands, which require at least SPSS Statistics 17 and the Python Programmability Plug-In, save the files into the extension subdirectory of your SPSS Statistics installation.  Use Utilities>Install Custom Dialog to install the dialog interface for SPSSINC CENSOR TABLES, and then restart SPSS Statistics.


These modules are the successor to the tables.py module that was used with SPSS 14 and 15.  The functionality is essentially the same, and the functions in tables17.py can be used directly in programs without the extension command apparatus.


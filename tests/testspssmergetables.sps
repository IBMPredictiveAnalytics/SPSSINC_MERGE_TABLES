get file='c:/spss16/samples/cars.sav'.
SPSSINC MERGE TABLES COMMAND=
"CTABLES  /TABLE year > mpg [MEAN count] BY origin"
 "/COMPARETEST TYPE=MEAN" MATCHLABEL="Mean".

SPSSINC MODIFY TABLES subtype="Custom Table" SELECT="<<ALL>>"
/STYLES APPLYTO=DATACELLS
CUSTOMFUNCTION="customstylefunctions.boldIfEndsWithPlainLetter".

get file="c:/spss17/samples/english/employee data.sav".
DATASET name employees.
* Custom Tables.
CTABLES
  /TABLE educ [C] > prevexp [S][MEAN] BY jobcat [C]
  /COMPARETEST TYPE=MEAN  ORIGIN=COLUMN.
SPSSINC MERGE TABLES MATCHLABEL="Mean".

SPSSINC MODIFY TABLES subtype="Custom Table" SELECT="<<ALL>>"
/STYLES APPLYTO=DATACELLS
CUSTOMFUNCTION="customstylefunctions.boldIfEndsWithPlainLetter".
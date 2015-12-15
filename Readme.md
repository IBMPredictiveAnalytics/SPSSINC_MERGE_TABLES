# SPSSINC MERGE TABLES
## Merge the contents of one pivot table in the Viewer into anot
 This procedure combines cell values from one table with v  alues in another table. The most common usage is to combine proportio  n or means test tables from Custom Tables with the main table, but ma  ny other kinds of merges are possible.

---
Requirements
----
- IBM SPSS Statistics 18 or later

---
Installation intructions
----
1. Open IBM SPSS Statistics
2. Navigate to Utilities -> Extension Bundles -> Download and Install Extension Bundles
3. Search for the name of the extension and click Ok. Your extension will be available.

---
Tutorial
----
SPSSINC MERGE TABLES COMMAND = "*command syntax to execute*"  
MATCHLABEL="*label where attaching*"  
MODE=MERGE^&#42;&#42; or REPLACE  
ROWFUNCTION="*row merging function*"  
COLFUNCTION="*column merging function*"  
PRIROWLEVELS=*list-of-numbers*  
PRICOLLEVELS=*list-of-numbers*  
SECROWLEVELS=*list-of-numbers*  
SECCOLLEVELS=*list-of-numbers*  
STANDARDFUNCTIONS=YES^&#42;&#42; or NO  
OMITSTATISTICSLEVEL=YES or NO^&#42;&#42;  
TABLES= primary^&#42; secondary^&#42;
where these are either absolute table numbers or OMS table subtypes
ATTACH=COLUMNS^&#42;&#42; or ROWS  

/OPTIONS HIDE=YES^&#42;&#42; or NO  
APPENDTITLE=YES^&#42;&#42; or NO  
APPENDCAPTION=YES^&#42;&#42; or NO  
HALIGN=LEFT or CENTER or RIGHT^&#42;&#42;  
ADDLABELLEAF={YES^&#42;&#42; or NO  
SEPARATOR="*text*"  
EXTRASEP=*number*  
LAYERFOOTNOTE="*text*" PRINTLEVELS=YES or NO^&#42;&#42;

/HELP

^&#42; Required  
^&#42;&#42; Default

SPSSINC MERGE TABLES /HELP prints this help and does nothing else.

Example: Merge the CTABLES column means table into the main table
```
SPSSINC MERGE TABLES command=
"CTABLES  /TABLE year [C][COUNT] BY origin [C]  /COMPARETEST TYPE=PROP"
mode=merge.
```

This example merges the CTABLES column means table into the main table based
on the column numbers using the supplied colfuncbynumber function to define
the columns to match.
```
SPSSINC MERGE TABLES MATCHLABEL="Mean" ATTACH=COLUMNS
MODE=MERGE COLFUNCTION="SPSSINC_MERGE_TABLES.colfuncbynumber" 
/OPTIONS HIDE=YES APPENDTITLE=YES APPENDCAPTION=YES ADDLABELLEAF=YES
HALIGN=RIGHT SEPARATOR="\n".
```

The next example merges two correlation tables together.
```
CORRELATIONS
/VARIABLES=mpg engine horse weight
/PRINT=TWOTAIL SIG
   /MISSING=PAIRWISE.
NONPAR CORR
/VARIABLES=mpg engine horse weight
/PRINT=KENDALL TWOTAIL SIG
/MISSING=PAIRWISE.

SPSSINC MERGE TABLES ATTACH=COLUMNS
MODE=MERGE PRIROWLEVELS=1 3 PRICOLLEVELS=1 STANDARDFUNCTIONS=NO 
ECROWLEVELS=3 5 SECCOLLEVELS=1 
TABLES="'Correlations'" "'Correlations'"
/OPTIONS HIDE=YES APPENDTITLE=YES APPENDCAPTION=YES
HALIGN=RIGHT SEPARATOR="\n" PRINTLEVELS=NO.
```

**COMMAND** is an optional command such as CTABLES to run before applying the merge.
If it is long, it can be written as
```COMMAND = "part1"  "part2" ...```  (Note that the literals are NOT joined with +).

**MATCHLABEL** specifies the label for the point where the merged table is attached.  It is the
lowest level section.  Case matters.  It defaults to "Count".  Note that it is not always visible
e.g., ```CTABLES /SLABELS VISIBLE=NO.```

**MODE** can be MERGE, the default, which means the merged table cell value is appended
to the primary table, or REPLACE, to replace the primary cell value with the merged value.

The four **LEVELS** keywords can be used to select which levels of the respective labels should
be used in matching the cells.  Each specification is a list of level numbers, starting with 0.
Use **PRINTLEVELS**=YES to determine what the levels are in the particular tables as many tables
have hidden label levels.

**ROWFUNCTION** and **COLFUNCTION** can be specified as module.function names to specify
the Python function that will be used to determine the join logic.  See details in the 
dialog box help and comments below.
The default rowfunction and colfunction attach the merge points to columns.

*STANDARDFUNCTIONS* determines whether the standard functions are used when a
ROW or COL function is not specified explicitly.

```rowfuncbynumber``` and ```colfuncbynumber``` are provided in this file for joining tables strictly
by the row and/or column numbers.

**TABLES**= *number number*
or
TABLES = "oms subtype" "oms subtype"  
can be used to select particular tables.  numbers are for the absolute item number in the Viewer.
"oms subtype" selects based on the most recent instances of a table of the specified type.
The first table in the pair is the primary table.

Specify **ATTACH**=ROWS to attach to rows, instead of columns.  For CTABLES,  the default functions
correspond to /SLABELS POSITION=COLUMN while ATTACH=ROWS corresponds
to /SLABELS POSITION=ROW.

By default, the secondary table is hidden after the merge.  **HIDE**=FALSE or NO prevents this.
**APPENDTITLE** and **APPENDCAPTION** can be set to FALSE or NO to prevent the automatic
addition of title and caption information to the primary table.

**HALIGN** can be LEFT, the default, CENTER, or RIGHT to set the horizontal alignment of
the cell after the merge.

By default, the merged and primary contents are separated by a newline. **SEPARATOR**
can set a different separator character or characters such as a blank.

**EXTRASEP** can specify that multiple copies of the separator sequence be used.
These two parameters have no effect if MODE=REPLACE.

Tables with layers are not supported in this function.  Only the top layer is merged.  In this
case, a footnote to this effect is automatically added.  Specify LAYERFOOTNOTE="text"
to provide different text (or "" to suppress it altogether).

Custom Merging Functions
------------------------
The following comments explain the main functions and how to write
custom merging functions.
There are three main functions: mergeLatest, mergeSelected, and
tmerge.  All have the same functionality but differ in how the participating tables are specified.

The functions stdrowfunc and stdcolfunc may also be useful if partially overriding the row and column
matching rules.

Example usage
```
begin program.
import tables

cmd=\
r'''CTABLES
    /TABLE sex > race [COUNT  COLPCT.COUNT] BY region
    /TITLES TITLE='This is the Main Table'
    /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN.
'''
SPSSINC_MERGE_TABLES.mergeLatest(cmd, label='Count')
end program.
```
This example runs a Ctables command and merges the last table in the Viewer, which has the signifcance tests, into the
main table, which has count and percent statistics in the columns.

The next example is similar but has the statistics in the rows.  This requires custom rowfunc and colfunc functions.
These functions determine the definition of the join between the two tables.  The custom rowfunc ensures that the rows
labeled Count in the main table match the corresponding rows in the significance table by removing the "Count" element of the
label, but they leave the other statistics labels unchanged to ensure that those do not join.

Secondly,  the colfunc function, when being applied to the test table -- othertable is True -- return the column heading without
the (A), (B) etc term ensuring that the columns join on the rest of the heading.  But on the main table, the entire column heading
is returned, because there is no statistic name in it (because that label occurs in the rows for this layout).
```
cmd=\
r'''CTABLES
    #/TABLE sex > race [COUNT  COLPCT.COUNT] BY region
    #/SLABELS POSITION=row
    #/TITLES TITLE='This is the Main Table'
    #/COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN.'''

#def rowfunc(tup, othertable, number):
    #if tup[-1] == 'Count':
        #return tup[0:-1]
    #else:
        #return tup

#def colfunc(tup, othertable, number):
    #if othertable:
        #return tup[:-1]
    #else:
        #return tup

#SPSSINC_MERGE_TABLES.mergeLatest(cmd, rowfunc = rowfunc, colfunc=colfunc)
```

This example merges two tables with the same structure but different statistics.
```
cmd=\
r'''CTABLES
    /TABLE region BY sex > educ [MEAN F10.3] by race.
CTABLES
    /TABLE region BY sex > educ [SEMEAN 'SE Mean' F10.3].
'''
SPSSINC_MERGE_TABLES.mergeLatest(cmd, label='Mean', mode='merge')
```

This example merges two tables with different statistics but only for males in the West region
```
cmd=\
r'''CTABLES
    /TABLE region BY sex > educ [MEAN F10.3] by race.
CTABLES
    #/TABLE region BY sex > educ [SEMEAN 'SE Mean' F10.3].
'''
def rowfunc(tup, othertable):
    if othertable and tup[-1] != "West":
        return None
    else:
        return SPSSINC_MERGE_TABLES.stdrowfunc(tup, othertable)

def colfunc(tup, othertable):
    if othertable and tup[2] != "Male":
        return None
    else:
        return SPSSINC_MERGE_TABLES.stdcolfunc(tup, othertable)

SPSSINC_MERGE_TABLES.mergeLatest(cmd, label='Mean', mode='merge', rowfunc = rowfunc, colfunc=colfunc)
```

---
License
----

- Apache 2.0
                              
Contributors
----

  - IBM SPSS

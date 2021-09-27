#/***********************************************************************
# * Licensed Materials - Property of IBM 
# *
# * IBM SPSS Products: Statistics Common
# *
# * (C) Copyright IBM Corp. 1989, 2020
# *
# * US Government Users Restricted Rights - Use, duplication or disclosure
# * restricted by GSA ADP Schedule Contract with IBM Corp. 
# ************************************************************************/
# extension command implementation for MERGE LATEST command


__author__ = "SPSS, JKP"
__version__ = "1.3.4"


# 14-sep-2009 Add ADDLABELLEAF to syntax support
# 14-dec-2009 Enable localization
#  19-apr-2010 Update help text, layerfootnote fix
# 27-feb-2011 Add ability to merge by row and/or column number instead of label
#    NOTE: this changes the interface to these functions.  User-written ones need to be updated.
# 11-oct-2011 Catch up with Statistics change in escape interpretation - make \n show up as newline
# 13-jan-2014 Add ADDOPPOSITE syntax
# 01-sep-2021 Change custom function import code due to Python 3 change.

import spss
if not int(spss.GetDefaultPlugInVersion()[4:6]) >= 17:
    raise ImportError(_("This module requires at least SPSS Statistics 17"))
import SpssClient, sys, time, re
from extension import floatex
from spssaux import GetSPSSVersion
import importlib
spssver = [int(i) for i in GetSPSSVersion().split('.')]
spssverLt1702 = spssver[:-1] < [17,0,2]
spssverLe1702 = spssver[:-1] <= [17,0,2]

global omitstatistics   # stores omitstatisticslevel value

from extension import Template, Syntax, processcmd
# debugging
        # makes debug apply only to the current thread
#try:
    #import wingdbstub
    #import threading
    #wingdbstub.Ensure()
    #wingdbstub.debugger.SetDebugThreads({threading.get_ident(): 1})
#except:
    #pass


helptext = r"""SPSS MERGE TABLES [command = "command syntax to execute"]
[MATCHLABEL="label where attaching"]
[MODE=merge** | replace]
[ROWFUNCTION="row merging function"]
[COLFUNCTION="column merging function"]
[PRIROWLEVELS=list-of-numbers]
[PRICOLLEVELS=list-of-numbers]
[SECROWLEVELS=list-of-numbers]
[SECCOLLEVELS=list-of-numbers]
[STANDARDFUNCTIONS={YES*|NO}]
[OMITSTATISTICSLEVEL={YES|NO*}]
TABLES= primary secondary
where these are either absolute table numbers or OMS table subtypes
[ATTACH=COLUMNS*|ROWS]

[/OPTIONS HIDE={YES*|NO} [APPENDTITLE={YES*|NO}] 
[APPENDCAPTION={YES*|NO}] [HALIGN={LEFT | CENTER | RIGHT**}]
[ADDLABELLEAF={YES*|NO}] [SEPARATOR="text" EXTRASEP=number]
[LAYERFOOTNOTE="text"] [PRINTLEVELS={YES|NO}]

[/HELP].

command is an optional command such as CTABLES to run before applying the merge.
If it is long, it can be written as
COMMAND = "part1"  "part2" ...  (Note that the literals are NOT joined with +.
MATCHLABEL specifies the label for the point where the merged table is attached.  It is the
lowest level section.  Case matters.  It defaults to "Count".  Note that it is not always visible
e.g., CTABLES /SLABELS VISIBLE=NO.
MODE can be merge, the default, which means the merged table cell value is appended
to the primary table, or replace, to replace the primary cell value with the merged value.

The four LEVELS keywords can be used to select which levels of the respective labels should
be used in matching the cells.  Each specification is a list of level numbers, starting with 0.
Use PRINTLEVELS=YES to determine what the levels are in the particular tables as many tables
have hidden label levels.

ROWFUNCTION and COLFUNCTION can be specified as module.function names to specify
the Python function that will be used to determine the join logic.  See details in the 
dialog box help and comments below.
The default rowfunction and colfunction attach the merge points to columns.
STANDARDFUNCTIONS determines whether the standard functions are used when a
ROW or COL function is not specified explicitly.

rowfuncbynumber and colfuncbynumber are provided in this file for joining tables strictly
by the row and/or column numbers.

TABLES= number number
or
TABLES = "oms subtype" "oms subtype"
can be used to select particular tables.  numbers are for the absolute item number in the Viewer.
"oms subtype" selects based on the most recent instances of a table of the specified type.
The first table in the pair is the primary table.

Specify ATTACH=ROWS to attach to rows, instead.  For CTABLES,  the default functions
correspond to /SLABELS POSITION=COLUMN while ATTACH=ROWS corresponds
to /SLABELS POSITION=ROW.


By default, the secondary table is hidden after the merge.  HIDE=FALSE or NO prevents this.
APPENDTITLE and APPENDCAPTION can be set to FALSE or NO to prevent the automatic
addition of title and caption information to the primary table.
HALIGN can be LEFT, the default, CENTER, or RIGHT to set the horizontal alignment of
the cell after the merge.
By default, the merged and primary contents are separated by a newline ("\n")  SEPARATOR
can set a different separator character or characters such as a blank.
EXTRASEP can specify that multiple copies of the separator sequence be used.
These two parameters have no effect if MODE=REPLACE.

Tables with layers are not supported in this function.  Only the top layer is merged.  In this
case, a footnote to this effect is automatically added.  Specify LAYERFOOTNOTE="text"
to provide different text (or "" to suppress it altogether).

Example,
SPSS MERGE TABLES command=
"CTABLES  /TABLE year [C][COUNT] BY origin [C]  /COMPARETEST TYPE=PROP"
mode=merge.

This example merges the CTABLES column means table into the main table based
on the column numbers using the supplied colfuncbynumber function to define
the columns to match.

SPSSINC MERGE TABLES MATCHLABEL="Mean" ATTACH=COLUMNS
MODE=MERGE COLFUNCTION="SPSSINC_MERGE_TABLES.colfuncbynumber" 
/OPTIONS HIDE=YES APPENDTITLE=YES APPENDCAPTION=YES ADDLABELLEAF=YES
HALIGN=RIGHT SEPARATOR="\n".


The next example merges two correlation tables together.
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


/HELP prints this help and does nothing else.

"""
# The following comments explain the main functions and how to write
# custom merging functions.
#There are three main functions: mergeLatest, mergeSelected, and
#tmerge.  All have the same functionality but differ in how the participating tables are specified.

#The functions stdrowfunc and stdcolfunc may also be useful if partially overriding the row and column
#matching rules.

#Example usage (1991 General Social Survey, installed with SPSS)
#begin program.
#import tables

#cmd=\
#r'''CTABLES
    #/TABLE sex > race [COUNT  COLPCT.COUNT] BY region
    #/TITLES TITLE='This is the Main Table'
    #/COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN.
#'''
#SPSSINC_MERGE_TABLES.mergeLatest(cmd, label='Count')
#end program.

#This example runs a Ctables command and merges the last table in the Viewer, which has the signifcance tests, into the
#main table, which has count and percent statistics in the columns.

#The next example is similar but has the statistics in the rows.  This requires custom rowfunc and colfunc functions.
#These functions determine the definition of the join between the two tables.  The custom rowfunc ensures that the rows
#labeled Count in the main table match the corresponding rows in the significance table by removing the "Count" element of the
#label, but they leave the other statistics labels unchanged to ensure that those do not join.

#Secondly,  the colfunc function, when being applied to the test table -- othertable is True -- return the column heading without
#the (A), (B) etc term ensuring that the columns join on the rest of the heading.  But on the main table, the entire column heading
#is returned, because there is no statistic name in it (because that label occurs in the rows for this layout).

#cmd=\
#r'''CTABLES
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


## This example merges two tables with the same structure but different statistics.
#cmd=\
#r'''CTABLES
    #/TABLE region BY sex > educ [MEAN F10.3] by race.
#CTABLES
    #/TABLE region BY sex > educ [SEMEAN 'SE Mean' F10.3].
#'''
#SPSSINC_MERGE_TABLES.mergeLatest(cmd, label='Mean', mode='merge')

## This example merges two tables with different statistics but only for males in the West region
#cmd=\
#r'''CTABLES
    #/TABLE region BY sex > educ [MEAN F10.3] by race.
#CTABLES
    #/TABLE region BY sex > educ [SEMEAN 'SE Mean' F10.3].
#'''
#def rowfunc(tup, othertable):
    #if othertable and tup[-1] != "West":
        #return None
    #else:
        #return SPSSINC_MERGE_TABLES.stdrowfunc(tup, othertable)

#def colfunc(tup, othertable):
    #if othertable and tup[2] != "Male":
        #return None
    #else:
        #return SPSSINC_MERGE_TABLES.stdcolfunc(tup, othertable)

#SPSSINC_MERGE_TABLES.mergeLatest(cmd, label='Mean', mode='merge', rowfunc = rowfunc, colfunc=colfunc)


def Run(args):
    """Execute the SPSS MERGE TABLES command"""
    args = args[list(args.keys())[0]]
    ###print args   #debug

    oobj = Syntax([
        Template("COMMAND", subc="",  ktype="literal", var="cmd", islist=True),
        Template("MATCHLABEL", subc="", ktype="literal", var="label"),
        Template("MODE", subc="", ktype="literal", var="mode"),
        Template("ROWFUNCTION", subc="", ktype="literal", var="rowfunc"),
        Template("COLFUNCTION", subc="", ktype="literal", var="colfunc"),
        Template("STANDARDFUNCTIONS",subc="",ktype="bool", var="standardfunctions"),
        Template("PRIROWLEVELS", subc="", ktype="int", var="prirowlevels", islist=True),
        Template("PRICOLLEVELS", subc="", ktype="int", var="pricollevels", islist=True),
        Template("SECROWLEVELS", subc="", ktype="int", var="secrowlevels", islist=True),
        Template("SECCOLLEVELS", subc="", ktype="int", var="seccollevels", islist=True),
        Template("OMITSTATISTICSLEVEL", subc="", ktype="bool", var="omitstatisticslevel"),
        Template("TABLES", subc="", ktype="str", var="tablepair", islist=True),
        Template("ATTACH", subc="", ktype="str", var="attach"),
        
        Template("HIDE", subc="OPTIONS",  ktype="bool", var="hide"),
        Template("HALIGN", subc="OPTIONS", ktype="str", var="halign"),
        Template("APPENDTITLE", subc="OPTIONS", ktype="bool", var="appendtitle"),
        Template("APPENDCAPTION", subc="OPTIONS", ktype="bool", var="appendcaption"),
        Template("SEPARATOR", subc="OPTIONS", ktype="literal", var="separator"),
        Template("EXTRASEP", subc="OPTIONS", ktype="int", var="extrasep", vallist=[0]),
        Template("LAYERFOOTNOTE", subc="OPTIONS", ktype="literal", var="layerfootnote"),
        Template("PRINTLEVELS", subc="OPTIONS", ktype="bool", var="printlevels"),
        Template("ADDLABELLEAF", subc="OPTIONS", ktype="bool", var="addlabelleaf"),
        Template("ADDOPPOSITE", subc="OPTIONS", ktype="bool", var="addopposite"),
        Template("ADJUSTVERTLABELALIGN", subc="OPTIONS", ktype="bool", 
            var="adjustvertlabelalign"),
        Template("HELP", subc="", ktype="bool")])

    # ensure localization function is defined
    global _
    try:
        _("---")
    except:
        def _(msg):
            return msg


    # A HELP subcommand overrides all else
    if "HELP" in args:
        #print helptext
        helper()
    else:
        processcmd(oobj, args, mergeLatest, lastchancef=funcs)

# The last-chance function is called just before the implementing function and can be used
#  to fix up paramters or do extra validation

def funcs(parms):
    """Convert string function names to their callables and handle other parameter mappings

    parms is the parsed parameter structure.
    It is a dictionary with keys of the variable names in the Syntax object."""

    if "cmd" in parms:
        parms["cmd"] = "\n".join(parms["cmd"])

    for f in ["rowfunc", "colfunc"]:
        if f in parms:
            parms[f] = resolvestr(parms[f])

    aligns = {"left": SpssClient.SpssHAlignTypes.SpssHAlLeft,
              "center": SpssClient.SpssHAlignTypes.SpssHAlCenter,
              "right": SpssClient.SpssHAlignTypes.SpssHAlRight}
    if "halign" in parms:
        parms["halign"] = aligns[parms["halign"]]  # values have already been validated

def resolvestr(afunc):
    """Return a callable for afunc

    afunc may be a callable object or a string in the form module.func to be imported"""

    if callable(afunc):
        return afunc
    else:
        bfunc = afunc.split(".")
        if len(bfunc) != 2:
            raise ValueError(_("Function reference %s not valid") % afunc)
        #exec("from %s import %s as f" % (bfunc[0], bfunc[1]))
        #return f
        m = importlib.import_module(bfunc[0])
        return getattr(m, bfunc[1])

debug = False

class ClientSession(object):
    """Manager for the SpssClient start/stop state

    This class assumes that all client sessions are handled via with ClientSession."""

    # ref counting client session calls keeps the client alive until the outermost caller
    # terminates
    count = 0
    def __enter__(self):
        """initialization for with statement"""
        if ClientSession.count == 0:
            try:
                SpssClient.StartClient()
            except:
                raise RuntimeError(_("SpssClient.StartClient failed."))
        ClientSession.count += 1
        return self

    def __exit__(self, type, value, tb):
        ClientSession.count -= 1
        if ClientSession.count <= 0:
            SpssClient.StopClient()
        return False


def mergeLatest(cmd=None, desout=None, label=None,tablepair=None, mode='merge', appendtitle=True, appendcaption=True, 
                rowfunc=None, colfunc=None,  prirowlevels=None, pricollevels=None,
                secrowlevels=None, seccollevels=None,
                hide=True, addlabelleaf=True, layerfootnote=None, 
                halign=SpssClient.SpssHAlignTypes.SpssHAlRight, autofit=True, separator="\n", extrasep=0, 
                attach=None, printlevels=False, standardfunctions=True, 
                omitstatisticslevel=None, addopposite=False, adjustvertlabelalign=True):
    """Run the command(s), cmd. and merge the specified tables.

    If cmd is empty or not supplied, it is not run, and the requisite tables should already exist.
    if tablepair, a duple, is specified, those can be the absolute table numbers to merge: main, other.
    Alternatively, both entries can be OMS subtypes.  Then the most recent instances of those subtypes
    are used.  The first item in the duple, in either case, is the primary table
    Otherwise, the most recent tables are used with the lower-numbered on as the primary.
    The expectation is the the Ctables command produced the main table and one table containing either
    column proportions or column means tests.
    Set label to the label of the statistic where the merge should appear.  Typically it would be "Count" or "Mean"
    (case matters).  If no label is specified, the results are merged to all matching columns.
    rowfunc and colfunc specify the label transformation functions to use.
    prirowlevels, pricollevels, secrowlevels, and seccollevels can be specified to select
    the particular label levels to use in the join operation.  These are processed before calling
    rowfunc and colfunc.
    mode may be merge (the default), or replace.
    Set appendtitle and appendcaption to False to suppress the corresponding append.
    desout can be specified as the handle to the designated Viewer.  If None, this module will find it.
    set hide=False to prevent the test table from being hidden.
    If the tables have layers, only the first layer is merged, and a footnote is added to the title indicating this.
    layerfootnote can provide alternative text or be set to "" to suppress the footnote.
    halign can be 1(right), 2(center), or 3(left) to set the cell horizontal alignment.
    autofit can be set to False to prevent an autofit after the table changes.
    extrasep (default=0) specifies the number of extra separator characters to append to the cell value.
    printlevels True causes table label levels to be displayed for debugging purposes
    if omitstatistcslevel is True, that levels will be removed in matching key.  If it is None, the level will
    be removed if matching custom tables objects
    """

    time.sleep(1.0)
    with ClientSession():
        if desout is None:
            desout= SpssClient.GetDesignatedOutputDoc()
        if spssverLe1702:
            prelimkt = desout.GetOutputItems().Size() -1   #set up to check for updated items object
        items = None
        if cmd:
            spss.Submit(cmd)
            if spssverLe1702:
                spss.Submit("_SYNC.")  # Be sure output is all created
            if spssverLe1702:
                for i in range(3):   #
                    items = desout.GetOutputItems()
                    itemkt = items.Size()-1
                    if itemkt > prelimkt:
                        break
                    time.sleep(.5)
        if items is None:
            if spssverLe1702:
                spss.Submit("_SYNC.")
            items = desout.GetOutputItems()
            itemkt = items.Size() - 1

        # The tablepair can be
        #  - empty: take the last two tables in the Viewer
        #  - two objects convertible to integers - take these objects
        #  - two OMS subtypes - search backwards for tables of these types.
        #    If both types are the same, the higher-numbered object is the secondary table
        if tablepair is None:
            tablepair = [None, None]	    
        tlen = len(tablepair)
        if tlen not in [0,2]:
            raise ValueError(_("Incorrect number of table objects specified: %s") % tlen)
        try:   # first try for all integer-like contents
            tablepair = [int(item) for item in tablepair]
        except:
            try:  # next look for item types and resolve to item numbers or search for newest tables in Viewer
                tablepair = ["".join(item.lower().split()) for item in tablepair]  # clear out type white space
                # clear out any matching outer quotes of either type
                tablepair = [re.sub(r"""(['"])(.*)\1""",r"\2", item) for item in tablepair]
            except:
                pass

            # resolve item types or None values to item numbers working backwards from the end of the Viewer
            while itemkt >= 0:    
                item = items.GetItemAt(itemkt)
                if item.GetType() == SpssClient.OutputItemType.PIVOT:  # a pivot table
                    subtype = "".join(item.GetSubType().lower().split())
                    if tablepair[1] is None or tablepair[1] == subtype:   # matches secondary table?
                        tablepair[1] = itemkt  # will never match a subtype
                    elif tablepair[0] is None or tablepair[0] == subtype:  # matches primary?
                        tablepair[0] = itemkt
                    if isinstance(tablepair[0], int) and isinstance(tablepair[1], int):   # both tables resolved to item numbers?
                        break
                itemkt -= 1
            if itemkt <= 0:
                raise ValueError(_("Exactly two table numbers or OMS subtypes must be specified or a requested table not found."))

        tmerge(items, tablepair[0], tablepair[1], label=label, hide=hide, rowfunc=rowfunc, colfunc=colfunc,mode=mode,
               addlabelleaf=addlabelleaf, appendtitle=appendtitle, appendcaption=appendcaption, halign=halign, 
               autofit=autofit, separator=separator, extrasep=extrasep, attach=attach,
               prirowlevels=prirowlevels, pricollevels=pricollevels, secrowlevels=secrowlevels, seccollevels=seccollevels,
               printlevels=printlevels, standardfunctions=standardfunctions, 
               omitstatisticslevel=omitstatisticslevel, layerfootnote=layerfootnote,
               addopposite=addopposite, adjustvertlabelalign=adjustvertlabelalign)

def mergeSelected(*args, **kwds):
    """Merge the last two tables currently selected in the Designated Viewer using the 
    later table as <other> and earlier as <main>.

    Arguments are the same as for tmerge except that the first three are supplied by this function."""

    time.sleep(1.0)
    with ClientSession():
        desout = SpssClient.GetDesignatedOutputDoc()
        items = desout.GetOutputItems()
        itemkt = items.Size() - 1
        tablepair = []
        while itemkt >= 0 and len(tablepair) < 2:
            if items.GetItemAt(itemkt).GetType() == SpssClient.OutputItemType.PIVOT and \
               items.GetItemAt(itemkt).IsSelected():  #a selected pivot table
                tablepair.insert(0, itemkt)
            itemkt-= 1
        if len(tablepair) != 2:
            raise ValueError(_("At least two table numbers must be specified."))
        tmerge(desout, tablepair[0], tablepair[1], *args, **kwds)

def tmerge(items, main, other, hide=True, label=None, mode='merge', rowfunc=None, colfunc=None,
           addlabelleaf=True, appendtitle=True, appendcaption=True, layerfootnote=None, 
           halign=SpssClient.SpssHAlignTypes.SpssHAlRight, autofit=True, separator="\n", extrasep=0,
           attach=None, prirowlevels=None, pricollevels=None, secrowlevels=None, seccollevels=None,
           printlevels=False, standardfunctions=True, omitstatisticslevel=None,
           addopposite=False, adjustvertlabelalign=True):
    """merge the cells of table other into table main for those where the row and column labels match.

    main and other are item numbers of the tables in the Designated Viewer, whose items are passed in items.
    If hide, then the "other" table is hidden after the merge.
    Label identifies the column statistic where the merged cells are placed.  If omitted, statistics are placed in every
    applicable column.
    rowfunc and colfunc are functions that transform the row and column label tuples before creating the dictionary key.
    These are expected to be callables.
    By default, rowfunc is the identity function and colfunc selects all but the last tuple element.
    If addlabeleaf is True, the last element of the "other" table column labels is appened to the matching labels
    of the main table.
    If the table has layers, which are not supported in this function currently, the layerfootnote is attached
    to the title.  You can supply alternative text via this parameter.  Use an empty string to suppress the footnote.
    halign can be SpssClient.SpssHAlignTypes.SpssHAlRight, ...Center, or ...Left to set the horizontal alignment of the cells
    autofit can be set to False to prevent an autofit operation after the changes.
    extrasep (default 0) specifies the number of extra separators to be appended to the cell."""

    global omitstatistics

    rowfunc, colfunc = buildfuncs(rowfunc, colfunc, prirowlevels, pricollevels, secrowlevels, seccollevels, 
                                  attach, label, printlevels, standardfunctions)
    mode = mode.lower()
    if not mode in ['merge','replace']:
        raise ValueError(_("mode must be merge or replace"))

    time.sleep(1.0)
    with ClientSession():
        #objItems = desviewer.GetOutputItems()
        objItems = items
        main = objItems.GetItemAt(main)
        other = objItems.GetItemAt(other)
        if main.GetType()  != SpssClient.OutputItemType.PIVOT or other.GetType() != SpssClient.OutputItemType.PIVOT:
            raise ValueError(_("A specified item is not a pivot table or does not exist."))
        if omitstatisticslevel is None:
            omitstatistics = main.GetSubType() == "Custom Table" and	\
                other.GetSubType() in ["Comparisons of Proportions", "Comparisons of Means"]            
        else:
            omitstatistics = omitstatisticslevel

        #PivotTable= other.ActivateTable()
        try:
            PivotTable = other.GetSpecificType()
        except:
            time.sleep(.5)
            PivotTable = other.GetSpecificType()  # give it another chance
        if hide:
            other.SetVisible(False)   #hide secondary first in order to minimize redraws.


        try:
            otherdict, cols = gettbl(PivotTable.RowLabelArray() , PivotTable.ColumnLabelArray(), PivotTable.DataCellArray(),
                                     rowfunc, colfunc)
            othertitle = PivotTable.GetTitleText()
            othercaption = PivotTable.GetCaptionText()
        finally:
            #other.Deactivate()   # make sure table is deactivated
            pass
        originalWidth = main.GetWidth()
        #PivotTable = main.ActivateTable()
        PivotTable = main.GetSpecificType()   #new
        try:
            layerwarning = PivotTable.LayerLabelArray().GetNumDimensions()> 0
            PivotTable.SetUpdateScreen(False)
            colarray = PivotTable.ColumnLabelArray()
            settbl(PivotTable, PivotTable.RowLabelArray() , colarray,PivotTable.DataCellArray(), otherdict, label,
                   rowfunc, colfunc, mode, halign=halign, separator=separator, extrasep=extrasep)
            if addlabelleaf:
                appendleaf(colarray, colfunc, label, cols, mode, separator=separator,
                    addopposite=addopposite, adjustvertlabelalign=adjustvertlabelalign)
            if appendtitle:
                PivotTable.SetTitleText(PivotTable.GetTitleText() + "\n" + othertitle)
            if appendcaption:
                PivotTable.SetCaptionText(PivotTable.GetCaptionText() + "\n" + othercaption)
            if autofit:
                PivotTable.Autofit()
        finally:
            if layerwarning and layerfootnote != "":
                PivotTable.SelectTitle()
                PivotTable.InsertFootnote(layerfootnote or _("Only the first layer has been merged from the secondary table."))
            PivotTable.SetUpdateScreen(True)
            ###main.Activate()
            ###main.Deactivate()
            #PivotTable.UpdateScreen = True
        #if hide:
        #	other.SetVisible(False)   #??? method of output item
    ##	main.Activate()
    ##	main.Deactivate()

def appendleaf(colarray, colfunc, label, cols, mode, separator="\n", 
        addopposite=False, adjustvertlabelalign=True):
    """append the leaf element of colarray to matching items in cols at label, if any.
    If mode != 'merge', then replace the leaf instead of appending."""

    separator = separator.replace(r"\n", "\n")  #V19 changed escape interpretation    
    merge = mode == 'merge'
    coldict = {}
    for i, tup in enumerate(cols):
        coldict[colfunc(tuple(tup),True, i)] = tup[-1]  #need to be able to trim here.  was False
    nr = colarray.GetNumRows()-1
    for j in range(colarray.GetNumColumns()):
        try:
            if adjustvertlabelalign and not spssverLt1702:   # can't set vertical alignment in 17.0.1 if any hidden layers in labels
                colarray.SetVAlignAt(nr, j, SpssClient.SpssVAlignTypes.SpssVAlTop)   #force vertical alignment
        except:
            pass
        if label is None or label == colarray.GetValueAt(nr,j) or addopposite:
            tbltup = colfunc(maketup(colarray, j, 'col'), False, j)
            if tbltup in coldict:
                if merge:
                    colarray.SetValueAt(nr,j,  colarray.GetValueAt(nr,j) + separator + coldict[tbltup])
                else:
                    colarray.SetValueAt(nr,j,  coldict[tbltup])


def gettbl(rowlabels, collabels, datacells, rowfunc, colfunc):
    """return dictionary indexed by rowlabel and collabel tuple of datacells values and a listof the row label tuples with col identifier
    Dictionary containing a duple of the datacell value and the column identifier for test purposes e.g., (A).
    rowfunc and colfunc are functions applied to the label tuples before using them as keys.
    """

    tbldict = {}
    cols = []
    for j in range(datacells.GetNumColumns()):	
        collabeltup = maketup(collabels, j, 'col')
        cols.append(collabeltup)
        for i in range(datacells.GetNumRows()):
            rowlabeltup = maketup(rowlabels, i, 'row')
            rf = rowfunc(rowlabeltup, True, i)
            cf = colfunc(collabeltup, True, j)
            # check for duplicate row,col label entry, but ignore cases where a label is None
            # None's can happen if the label transformation functions are discarding portions of a table.
            if rf is not None and cf is not None and (rf, cf) in tbldict:
                raise ValueError(_("""Tables cannot be merged: The secondary table labels are not unique.
First duplicate row and column labels after transformation:
%s\n
%s""") % (rf, cf))
            tbldict[(rf, cf)] = fmtcell(datacells, i, j)
    return tbldict, cols

def maketup(obj, index, dim):
    "return tuple of row or column values of obj"
    lis = []
    if dim == 'row':
        for i in range(obj.GetNumColumns()):
            lis.append(obj.GetValueAt(index, i))
    else:
        for j in range(obj.GetNumRows()):
            lis.append(obj.GetValueAt(j, index))
    return tuple(lis)

def settbl(pt, rowlabels, collabels, datacells, tbldict, label, rowfunc, colfunc, mode,  
           halign=SpssClient.SpssHAlignTypes.SpssHAlRight, separator="\n", extrasep=0):
    """Modify table to incorporate "other" nonblank table values.  

    Set all cell vertical alignments to top to insure they still line up if separator has a line break
    and horizontal to right aligned for elements converted to strings.
    If, however, mode == 'replace' the values from the other table just replace the main table values.
    other formatting is preserved, but horizontal alignment may be changed.
    rowfunc and colfunc are functions applied to the label tuples before using them as keys.
    separator is inserted between the existing label and the attachment.
    halign can be 1 (right), 2(center), or 3(left)
    extraset can be used to specify the number (default 0) of extra separator sequences to follow the cell value in merge mode."""

    mergemode = mode == 'merge'
    # Version 19 has changed the way escapes are transmitted
    separator = separator.replace(r"\n", "\n")
    for i in range(datacells.GetNumRows()):
        rowlabeltup = maketup(rowlabels, i, 'row')
        for j in range(datacells.GetNumColumns()):
            #if mergemode:
                #try:
                    #datacells.SetVAlignAt(i,j, SpssClient.SpssVAlignTypes.SpssVAlTop)   #vertical alignment = SpssVAlTop #prof
                    #pass
                #except:
                    #pass
            collabeltup = maketup(collabels, j, 'col')
            key = (rowfunc(rowlabeltup,False, i), colfunc(collabeltup, False, j))
            otherval = tbldict.get(key, None)
            # If we have a value to attach and the statistics label matches or is not specified, do the attachment
            # Since the merge direction is not known, check both row and column for statistics label.  This could be fooled.
            if otherval is not None:
                if (label is None or collabeltup[-1].upper() == label.upper() or rowlabeltup[-1].upper() == label.upper()) \
                   and not str(otherval).isspace():

                    dataval = datacells.GetValueAt(i,j)
                    if dataval != "" or not spssverLt1702:  # versions prior to 17.0.2 cannot handle insertions in empty cells
                        if mergemode:
                            newval = fmtcell(datacells, i, j) + separator + str(otherval) + extrasep * separator
                            # percent formats are insisting on extra trailing %
                            try:
                                f = datacells.GetNumericFormatAt(i,j)
                                if f == "##.#%":
                                    datacells.SetNumericFormatAt(i,j, "#.#")
                            except:
                                pass
                            datacells.SetValueAt(i,j, " " + newval)
                            datacells.SetHAlignAt(i ,j,halign)  # right align cell
                        else:
                            if isinstance(otherval, str) and not isinstance(datacells.GetValueAt(i,j), str):
                                datacells.SetHAlignAt(i, j, halign)  # right align cell
                            datacells.SetValueAt(i, j, otherval)   # keep target table formatting (mostly).
    if mergemode and "\n" in separator:
        pt.ClearSelection()
        pt.SelectTableBody()
        pt.SetVAlign(SpssClient.SpssVAlignTypes.SpssVAlTop)
        pt.ClearSelection()



def fmtcell(cells, i, j):
    """return formatted value of cell(i,j).  If format matches some #.# or ##.#%, appropriate string is returned; otherwise
    simple formatting is used.  If the value appears to have a footnote attached to sysmis, None is returned."""
    value = cells.GetValueAt(i,j)
    #footnote markers are in the returned cell value :-(
    # In some SPSS versions, the GetCount api always returns 0.
    fno = cells.GetReferredFootnotesAt(i,j)

    try:
        fnc = fno.GetCount()  # hope that footnotes are all single digit.  Exception is raised if count is zero.
        if fnc > 0:
            fnc += fnc-1   # allow for a comma between each footnote marker
            value = value[:-fnc]
    except:
        pass
    if value in [".", ".,", ".a", ".b", ".c", ".d"] :   # working around problem with GetCount api in V18
        return None
    else:
        return value
    #fmt = cells.GetNumericFormatAt(i,j)
    #decimals = cells.GetHDecDigitsAt(i,j)
    #if fmt.startswith("#") or fmt.startswith("$"):
    #	try:
    #		value = "%.*f" % (decimals, value)
    #		if fmt.startswith("$"):
    #			value = "$" + value
    #		if fmt.endswith("%"):
    #			value = value + "%"
    #	except:
    #		if value[0] == "." and value[1].isalpha():
    #			value = None
    #		else:
    #			value = unicode(value)
    #else:
    #	value = unicode(value)
    #return value

# These functions are used by default to transform row and column label tuples when accessing the main or
# other table.

def stdrowfunc(tup,othertable, number):
    """tup is the tuple of row labels for the current row.  By default it is passed back unmodified.
    You can supply your own rowfunc to transform it when the tables being merged do not have the
    same structure or if you want to prevent the merging of certain rows.  Note that the tuple
    starts with "row" or "column", so the first normally visible element is tup[1].
    othertable is True if the function was called while processing the "other" table
    and False if processing the main table."""
    if debug:
        print(("row:", (othertable and "other:" or "main:"), tup))
    if omitstatistics:
        tup = tuple([item for item in tup if item != _("Statistics")])
    return tup

def stdcolfunc(tup, othertable, number):
    """tup is the tuple of column labels for the current column.  By default it is passed back with the
    last item deleted.  See additional comments under rowfunc"""
    if debug:
        print(("col:", (othertable and "other:" or "main:"), tup))
    if omitstatistics:
        tup = tuple([item for item in tup if item != _("Statistics")])
    return tup[:-1]

def exactcolfunc(tup, othertable, number):
    """use the entire label tuple without edits"""

    return tup

def buildfuncs(rowfunc, colfunc, prirowlevels, pricollevels, secrowlevels, seccollevels, attach, label, printlevels, standardfunctions):
    """Build row and column transformation functions and return a duple of functions

    rowfunc and cofunc are user-specified row and column label transformation functions or None
    Remaining parameters are lists of level numbers to be used prior to or in place of rowfunc and colfunc
    If no rowlevels are specified and rowfunc is None, the standard row function is used, but if row levels
    are specified and no row function is specified, only the row level filtering is applied.
    Similarly with columns.
    If attach == col and custom functions are not used and there is no filtering, the alt rowfunc and colfunc are used.
    printlevels True causes first row and column label levels to be printed for both tables.
    If standardfunctions is False, they are not called even though no custom functions are named."""

    if attach in ["rows", "rowsnostats"]:
        stdrfunc = makealtrowfunc(label)
        stdcfunc = altcolfunc
    else:
        stdrfunc = stdrowfunc
        stdcfunc = stdcolfunc
    if not rowfunc and standardfunctions:
        rowfunc = stdrfunc
    if not colfunc and standardfunctions:
        colfunc = stdcfunc
    # build closure functions for rows and columns
    # Note, the return values have to be hashable.

    dbglist = 4 * [printlevels]   # debug printing settings
    dbglabels = ["Primay Row", "Primary Column", "Secondary Row", "Secondary Column"]

    #select out label levels if any and call standard function, if any
    def rowfuncwrap(tup, othertable, number):
        printdbg(othertable, "row", tup, 0)
        try:
            try:
                if othertable and secrowlevels:
                    tup = tuple([tup[item] for item in secrowlevels])
                elif not othertable and prirowlevels:
                    tup = tuple([tup[item] for item in prirowlevels])
            except:
                raise ValueError(_("""A row label level is out of range.  Labels: %s, Index: %s""") % (tup, item)) 
            if rowfunc:
                tup = rowfunc(tup, othertable, number)					
        finally:
            printdbg(othertable, "row", tup, 1)
        return tup

    #select out label levels if any and call standard function, if any
    def colfuncwrap(tup, othertable, number):
        printdbg(othertable, "col", tup, 0)
        try:
            try:
                if othertable and seccollevels:
                    tup = tuple([tup[item] for item in seccollevels])
                elif not othertable and pricollevels:
                    tup = tuple([tup[item] for item in pricollevels])
            except:
                raise ValueError(_("""A column label level is out of range.  Labels: %s, Index: %s""") % (tup, item))
            if colfunc:
                tup = colfunc(tup, othertable, number)
        finally:
            printdbg(othertable, "col", tup, 1)
        return tup

    def printdbg(sectable, dimension, tup, state):
        """Print first row and column for primary and secondary tables."""
        # sectable is T/F for secondary, primary table
        # dimension is "row" or "column"
        # tup is the label tuple
        # state is 0 for before transformation and 1 for after

        # closure using lists defined above, indexed by table type and dimension

        index = 2 * sectable + (dimension=="col")
        if dbglist[index]:
            if state == 1:
                dbglist[index]=False
            print(("\nTable Label Levels of First Cell: %s" % dbglabels[index]))
            print((["Before Transformation", "After Transformation"][state]))
            for i, lbl in enumerate(tup):
                print((i, lbl))

    return (rowfuncwrap, colfuncwrap)

# row-oriented merge functions
def makealtrowfunc(label):
    """make a closure with appropriate attachment label

    label is the text for matching.
    A None label will never match, so the entire tuple will always be returned in that case."""

    def altrowfunc(tup, othertable, number):
        if tup[-1] == label:
            if omitstatistics:
                tup = tuple([item for item in tup if item != _("Statistics")])
            return tup[0:-1]
        else:
            if omitstatistics:
                tup = tuple([item for item in tup if item != _("Statistics")])
            return tup
    return altrowfunc

def altcolfunc(tup, othertable, number):
    if othertable:
        if omitstatistics:
            tup = tuple([item for item in tup if item != _("Statistics")])
        return tup[:-1]
    else:
        if omitstatistics:
            tup = tuple([item for item in tup if item != _("Statistics")])
        return tup
    
def rowfuncbynumber(tup,othertable, number):
    """tup is the tuple of row labels for the current row.  By default it is passed back unmodified.
    
    You can supply your own rowfunc to transform it when the tables being merged do not have the
    same structure or if you want to prevent the merging of certain rows.  Note that the tuple
    starts with "row" or "column", so the first normally visible element is tup[1].
    
    othertable is True if the function was called while processing the "other" table
    and False if processing the main table.
    
    number is the row number of the table.  If the join is just by position, you can use
    this function to align the tables even if the labels are not unique
    
    to use this function, specify ROWFUNCTION=SPSSINC_MERGE_TABLES.rowfuncbynumber"""
    

    if debug:
        print(("row:", (othertable and "other:" or "main:"), number, tup))


    tup = (str(number),)
    return tup

def colfuncbynumber(tup, othertable, number):
    """tup is the tuple of column labels for the current column.  By default it is passed back with the
    last item deleted.  See additional comments under rowfuncbynumber
    
    This version can be used to match just by column number.
    With multiple statistics you might need to adjust the number calculation, e.g., number % 2"""
    if debug:
        print(("col:", (othertable and "other:" or "main:"), tup))

    return (str(number),)


def helper():
    """open html help in default browser window
    
    The location is computed from the current module name"""
    
    import webbrowser, os.path
    
    path = os.path.splitext(__file__)[0]
    helpspec = "file://" + path + os.path.sep + \
         "markdown.html"
    
    # webbrowser.open seems not to work well
    browser = webbrowser.get()
    if not browser.open_new(helpspec):
        print(("Help file not found:" + helpspec))
try:    #override
    from extension import helper
except:
    pass
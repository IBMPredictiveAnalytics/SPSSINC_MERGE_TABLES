#/***********************************************************************
# * Licensed Materials - Property of IBM 
# *
# * IBM SPSS Products: Statistics Common
# *
# * (C) Copyright IBM Corp. 1989, 2011
# *
# * US Government Users Restricted Rights - Use, duplication or disclosure
# * restricted by GSA ADP Schedule Contract with IBM Corp. 
# ************************************************************************/

from __future__ import with_statement

r"""Part 1:Functions to merge similar pivot tables;  Part2: Functions to censor table cells based on associated statistics."""

r"""Part 1:There are three main functions: mergeLatest, mergeSelected, and
tmerge.  All have the same functionality but differ in how the participating tables are specified.

The functions stdrowfunc and stdcolfunc may also be useful if partially overriding the row and column
matching rules.

Example usage (1991 General Social Survey, installed with SPSS)
begin program.
import tables

cmd=\
r'''CTABLES
  /TABLE sex > race [COUNT  COLPCT.COUNT] BY region
  /TITLES TITLE='This is the Main Table'
  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN.
'''
tables17.mergeLatest(cmd, label='Count')
end program.

This example runs a Ctables command and merges the last table in the Viewer, which has the signifcance tests, into the
main table, which has count and percent statistics in the columns.

The next example is similar but has the statistics in the rows.  This requires custom rowfunc and colfunc functions.
These functions determine the definition of the join between the two tables.  The custom rowfunc ensures that the rows
labeled Count in the main table match the corresponding rows in the significance table by removing the "Count" element of the
label, but they leave the other statistics labels unchanged to ensure that those do not join.

Secondly,  the colfunc function, when being applied to the test table -- othertable is True -- return the column heading without
the (A), (B) etc term ensuring that the columns join on the rest of the heading.  But on the main table, the entire column heading
is returned, because there is no statistic name in it (because that label occurs in the rows for this layout).

cmd=\
r'''CTABLES
  /TABLE sex > race [COUNT  COLPCT.COUNT] BY region
 /SLABELS POSITION=row
 /TITLES TITLE='This is the Main Table'
  /COMPARETEST TYPE=PROP ALPHA=0.05 ADJUST=BONFERRONI ORIGIN=COLUMN.'''

def rowfunc(tup, othertable):
	if tup[-1] == 'Count':
		return tup[0:-1]
	else:
		return tup

def colfunc(tup, othertable):
	if othertable:
		return tup[:-1]
	else:
		return tup

tables17.mergeLatest(cmd, rowfunc = rowfunc, colfunc=colfunc)


# This example merges two tables with the same structure but different statistics.
cmd=\
r'''CTABLES
  /TABLE region BY sex > educ [MEAN F10.3] by race.
CTABLES
  /TABLE region BY sex > educ [SEMEAN 'SE Mean' F10.3].
'''
tables17.mergeLatest(cmd, label='Mean', mode='merge')

# This example merges two tables with different statistics but only for males in the West region
cmd=\
r'''CTABLES
  /TABLE region BY sex > educ [MEAN F10.3] by race.
CTABLES
  /TABLE region BY sex > educ [SEMEAN 'SE Mean' F10.3].
'''
def rowfunc(tup, othertable):
	if othertable and tup[-1] != "West":
		return None
	else:
		return tables17.stdrowfunc(tup, othertable)

def colfunc(tup, othertable):
	if othertable and tup[2] != "Male":
		return None
	else:
		return tables17.stdcolfunc(tup, othertable)

tables17.mergeLatest(cmd, label='Mean', mode='merge', rowfunc = rowfunc, colfunc=colfunc)



Part 2: Functions to censor table cells.


Example: censorLatest
This example blanks out the means for all cells with a count value < 100.  See the function help for other censoring options.
cmd='ctables   /TABLE origin BY accel [MEAN, COUNT]'
rc=tables17.censorLatest(critvalue=100, desout=desout, neighborlist=[-1], direction='row')

Example: blank out insignificant correlations from CORRELATIONS.

cmd=r"CORRELATIONS  /VARIABLES=availblt avg_purc chckout"
tables17.censorLatest(cmd=cmd, critvalue=.01, critfield="Sig. (2-tailed)", 
    testtype=">", neighborlist=[0,1,-1], direction='column')
"""

# This module will not work in distributed mode or if there is not a regular Designated Viewer.
#  Tables with layers are not supported for the merge functions.  The first layer is processed, and a footnote is attached.
#  The censoring functions do support layers.

# In order to avoid display problems in some older releases, set the SPSS pivot table options to "edit all tables in the Viewer".
# However, display problems can be cleared up by activating and deactivating a table
# and the table will export or print properly without this step.

# The first set of code provides ways to merge two tables together.
# There are three main functions: mergeLatest, mergeSelected, and tmerge.
# The functions mergeLatest and tmerge are very similar.  mergeLatest includes the ability to specify a set of
# SPSS commands to run and an automatic way to find the last tables.

# The second set of code provides ways to censor cells of a table based on a statistic.  Typically it would be
# used to blank out cells where the count for that category is too small

# Copyright(c) SPSS Inc, 2007, 2008



__author__ =  'JKP'
__version__=  '2.3.4'

# history
# 07-apr-2006  Initial experimental version
# 11-apr-2006   Add mode parameter to allow merge or replace of cells, and othertable parameter to rowfunc and colfunc
#                          to allow these functions to distinguish between the main and other tables.  Added mergeSelected.
# 05-jan-2007   Added functions for censoring table cells.
# 03-feb-2007  Added option to hide entire criterion column when censoring a table
# 22-jan-2008  Conversion for SPSS 16
# 11-jul- 2008   Conversion for SPSS 17
# 17-sep-2008  Modifications to censoring functions for extension command
# 19-dec-2008  New features for label filtering and dialog box support.
#  07-may-2009 Add workaround for footnote-in-text problem <= 17.0.2 and change cell fmt if pct and merging.
#  04-oct-2009  Add ability to ignore Statistics level in labels and use automatically for certain Ctables merges
#  05-oct-2009  Gain a lot of speed by using selection for vertical alignment
#  15-nov-2009  Ignore redundant outer quotes in censorLatest

#try:
	#import wingdbstub
#except:
	#pass


import spss
if not int(spss.GetDefaultPlugInVersion()[4:6]) >= 17:
	raise ImportError("This module requires at least SPSS Statistics 17")
import SpssClient, sys, time, re
from extension import floatex
from spssaux import GetSPSSVersion
spssver = [int(i) for i in GetSPSSVersion().split('.')]
spssverLt1702 = spssver[:-1] < [17,0,2]
spssverLe1702 = spssver[:-1] <= [17,0,2]

global omitstatistics   # stores omitstatisticslevel value


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
				raise RuntimeError("SpssClient.StartClient failed.")
		ClientSession.count += 1
		return self

	def __exit__(self, type, value, tb):
		ClientSession.count -= 1
		if ClientSession.count <= 0:
			SpssClient.StopClient()
		return False

debug = False

def mergeLatest(cmd=None, desout=None, label=None,tablepair=None, mode='merge', appendtitle=True, appendcaption=True, 
				rowfunc=None, colfunc=None,  prirowlevels=None, pricollevels=None,
				secrowlevels=None, seccollevels=None,
				hide=True, addlabelleaf=True, layerfootnote=None, 
				halign=SpssClient.SpssHAlignTypes.SpssHAlRight, autofit=True, separator="\n", extrasep=0, 
				attach=None, printlevels=False, standardfunctions=True, omitstatisticslevel=None):
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
			raise ValueError("Incorrect number of table objects specified: %s" % tlen)
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
				raise ValueError("Exactly two table numbers or OMS subtypes must be specified or a requested table not found.")

		tmerge(items, tablepair[0], tablepair[1], label=label, hide=hide, rowfunc=rowfunc, colfunc=colfunc,mode=mode,
			   addlabelleaf=addlabelleaf, appendtitle=appendtitle, appendcaption=appendcaption, halign=halign, 
			   autofit=autofit, separator=separator, extrasep=extrasep, attach=attach,
			   prirowlevels=prirowlevels, pricollevels=pricollevels, secrowlevels=secrowlevels, seccollevels=seccollevels,
			   printlevels=printlevels, standardfunctions=standardfunctions, omitstatisticslevel=omitstatisticslevel)

def mergeSelected(*args, **kwds):
	"""Merge the last two tables currently selected in the Designated Viewer using the 
	later table as <other> and earlier as <main>.
	
	Arguments are the same as for tmerge except that the first three are supplied by this function."""

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
			raise ValueError, "At least two table numbers must be specified."
		tmerge(desout, tablepair[0], tablepair[1], *args, **kwds)

def tmerge(items, main, other, hide=True, label=None, mode='merge', rowfunc=None, colfunc=None,
	addlabelleaf=True, appendtitle=True, appendcaption=True, layerfootnote=None, 
	halign=SpssClient.SpssHAlignTypes.SpssHAlRight, autofit=True, separator="\n", extrasep=0,
	attach=None, prirowlevels=None, pricollevels=None, secrowlevels=None, seccollevels=None,
	printlevels=False, standardfunctions=True, omitstatisticslevel=None):
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
		raise ValueError, "mode must be merge or replace"

	with ClientSession():
		#objItems = desviewer.GetOutputItems()
		objItems = items
		main = objItems.GetItemAt(main)
		other = objItems.GetItemAt(other)
		if main.GetType()  != SpssClient.OutputItemType.PIVOT or other.GetType() != SpssClient.OutputItemType.PIVOT:
			raise ValueError, "A specified item is not a pivot table or does not exist."
		if omitstatisticslevel is None:
			if main.GetSubType() == "Custom Table" and	other.GetSubType() in ["Comparisons of Proportions", "Comparisons of Means"]:
				omitstatistics = True
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
			layerwarning = PivotTable.LayerLabelArray().GetNumDimensions()> 1 
			PivotTable.SetUpdateScreen(False)
			colarray = PivotTable.ColumnLabelArray()
			settbl(PivotTable, PivotTable.RowLabelArray() , colarray,PivotTable.DataCellArray(), otherdict, label,
				   rowfunc, colfunc, mode, halign=halign, separator=separator, extrasep=extrasep)
			if addlabelleaf:
				appendleaf(colarray, colfunc, label, cols, mode, separator=separator)
			if appendtitle:
				PivotTable.SetTitleText(PivotTable.GetTitleText() + "\n" + othertitle)
			if appendcaption:
				PivotTable.SetCaptionText(PivotTable.GetCaptionText() + "\n" + othercaption)
			if autofit:
				PivotTable.Autofit()
		finally:
			if layerwarning and layerfootnote != "":
				PivotTable.SelectTitle()
				PivotTable.InsertFootnote(layerfootnote or "Only the first layer has been merged from the secondary table.")
			PivotTable.SetUpdateScreen(True)
			###main.Activate()
			###main.Deactivate()
			#PivotTable.UpdateScreen = True
		#if hide:
		#	other.SetVisible(False)   #??? method of output item
	##	main.Activate()
	##	main.Deactivate()

def appendleaf(colarray, colfunc, label, cols, mode, separator="\n"):
	"""append the leaf element of colarray to matching items in cols at label, if any.
	If mode != 'merge', then replace the leaf instead of appending."""

	merge = mode == 'merge'
	coldict = {}
	for tup in cols:
		coldict[colfunc(tuple(tup),True)] = tup[-1]  #need to be able to trim here.  was False
	nr = colarray.GetNumRows()-1
	for j in range(colarray.GetNumColumns()):
		try:
			if not spssverLt1702:   # can't set vertical alignment in 17.0.1 if any hidden layers in labels
				colarray.SetVAlignAt(nr, j, SpssClient.SpssVAlignTypes.SpssVAlTop)   #force vertical alignment
		except:
			pass
		if label is None or label == colarray.GetValueAt(nr,j):
			tbltup = colfunc(maketup(colarray, j, 'col'), False)
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
			rf = rowfunc(rowlabeltup, True)
			cf = colfunc(collabeltup, True)
			# check for duplicate row,col label entry, but ignore cases where a label is None
			# None's can happen if the label transformation functions are discarding portions of a table.
			if rf is not None and cf is not None and (rf, cf) in tbldict:
				raise ValueError("""Tables cannot be merged: The secondary table labels are not unique.
First duplicate row and column labels after transformation:
%s\n
%s""" % (rf, cf))
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
			key = (rowfunc(rowlabeltup,False), colfunc(collabeltup, False))
			otherval = tbldict.get(key, None)
			# If we have a value to attach and the statistics label matches or is not specified, do the attachment
			# Since the merge direction is not known, check both row and column for statistics label.  This could be fooled.
			if otherval is not None:
				if (label is None or collabeltup[-1].upper() == label.upper() or rowlabeltup[-1].upper() == label.upper()) \
				   and not unicode(otherval).isspace():
					
					dataval = datacells.GetValueAt(i,j)
					if dataval != "" or not spssverLt1702:  # versions prior to 17.0.2 cannot handle insertions in empty cells
						if mergemode:
							newval = fmtcell(datacells, i, j) + separator + unicode(otherval) + extrasep * separator
							# percent formats are insisting on extra trailing %
							try:
								f = datacells.GetNumericFormatAt(i,j)
								if f == u"##.#%":
									datacells.SetNumericFormatAt(i,j, u"#.#")
							except:
								pass
							datacells.SetValueAt(i,j, " " + newval)
							datacells.SetHAlignAt(i ,j,halign)  # right align cell
						else:
							if isinstance(otherval, basestring) and not isinstance(datacells.GetValueAt(i,j), basestring):
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
	fno = cells.GetReferredFootnotesAt(i,j)
	try:
		fnc = fno.GetCount()  # hope that footnotes are all single digit.  Exception is raised if count is zero.
		if fnc > 0:
			fnc += fnc-1   # allow for a comma between each footnote marker
			value = value[:-fnc]
	except:
		pass
	if value in [".", ".,"] :
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

def stdrowfunc(tup,othertable):
	"""tup is the tuple of row labels for the current row.  By default it is passed back unmodified.
	You can supply your own rowfunc to transform it when the tables being merged do not have the
	same structure or if you want to prevent the merging of certain rows.  Note that the tuple
	starts with "row" or "column", so the first normally visible element is tup[1].
	othertable is True if the function was called while processing the "other" table
	and False if processing the main table."""
	if debug:
		print "row:", (othertable and "other:" or "main:"), tup
	if omitstatistics:
		tup = tuple([item for item in tup if item != "Statistics"])		
	return tup

def stdcolfunc(tup, othertable):
	"""tup is the tuple of column labels for the current column.  By default it is passed back with the
	last item deleted.  See additional comments under rowfunc"""
	if debug:
		print "col:", (othertable and "other:" or "main:"), tup
	if omitstatistics:
		tup = tuple([item for item in tup if item != "Statistics"])
	return tup[:-1]

def exactcolfunc(tup, othertable):
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
	def rowfuncwrap(tup, othertable):
		printdbg(othertable, "row", tup, 0)
		try:
			try:
				if othertable and secrowlevels:
					tup = tuple([tup[item] for item in secrowlevels])
				elif not othertable and prirowlevels:
					tup = tuple([tup[item] for item in prirowlevels])
			except:
				raise ValueError("""A row label level is out of range.  Labels: %s, Index: %s""" % (tup, item)) 
			if rowfunc:
				tup = rowfunc(tup, othertable)					
		finally:
			printdbg(othertable, "row", tup, 1)
		return tup
	
	#select out label levels if any and call standard function, if any
	def colfuncwrap(tup, othertable):
		printdbg(othertable, "col", tup, 0)
		try:
			try:
				if othertable and seccollevels:
					tup = tuple([tup[item] for item in seccollevels])
				elif not othertable and pricollevels:
					tup = tuple([tup[item] for item in pricollevels])
			except:
				raise ValueError("""A column label level is out of range.  Labels: %s, Index: %s""" % (tup, item))
			if colfunc:
				tup = colfunc(tup, othertable)
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
			print "\nTable Label Levels of First Cell: %s" % dbglabels[index]
			print ["Before Transformation", "After transformation"][state]
			for i, lbl in enumerate(tup):
				print i, lbl
			
	return (rowfuncwrap, colfuncwrap)
	


# Part 2
def censorLatest(cmd=None, desout=None, tablenum=None, critfield='Count', subtype=None,
				 critvalue=5, symbol=" ",  neighborlist=[1], direction='row', testtype="<", appendcaption=True,
				 othercaption=None, hidecrit=False):
	"""Run the command(s), cmd and censor specified cells based on criterion and return the number of cells censored.

	If cmd is empty or not supplied, it is not run, and the requisite tables should already exist.
	if tablenum is specified, it is the absolute table number to process.
	Otherwise, the most recent table is used.
	If subtype is specified, the most recent table with that OMS subtype is used.  If
	subtype has a redundant pair of outer quotes as would be produced from Copy OMS Subtype,
	they are ignored.
	Set appendtitle and appendcaption to False to suppress the corresponding append.
	desout can be specified as the handle to the designated Viewer.  If None, this module will find it.

	critfield specifies the leaf text of the cell to use for the criterion value.
	critvalue is the threshold value.  The absolute value of a cell is tested against the criterion value.
	neighborlist is a list of relative positions that should be censored.  Positive to the right/above,
	negative to the left/below.  In order to censor the criterion field itself, include 0 in neighborlist
	direction is 'row' for items in the same row or 'column' for items in the same column.
	The label is expected in the dimension opposite to direction.
	symbol is the value that should replace a censored field, defaulting to blank.
	hidecrit if True causes the criterion row or column to be hidden.

	Note that censoring a field may still leave its value discoverable if it is included in a total.

	Example: censor statistics in  a table when counts are small:
	cmd="CTABLES /TABLE origin BY accel [MEAN, COUNT]  /SLABELS POSITION=ROW."
    rc= tables17.censorLatest(critvalue=10, desout=desout, neighborlist=[-1], direction='column')

	Example: blank out insignificant correlations in the output from CORRELATIONS:
	cmd=r"CORRELATIONS  /VARIABLES=availblt avg_purc chckout"
    tables17.censorLatest(cmd=cmd, critvalue=.01, critfield="Sig. (2-tailed)", 
	    testtype=">", neighborlist=[0,1,-1], direction='column')

	"""
	if subtype:
		subtype = "".join(subtype.lower().split())
		subtype = re.sub(r"""(['"])(.*)\1""",r"\2", subtype)
	if cmd:
		spss.Submit(cmd)
	with ClientSession():
		if desout is None:
			desout= SpssClient.GetDesignatedOutputDoc()
		if not tablenum:
			if spssverLe1702:
				spss.Submit("_SYNC.")
			items = desout.GetOutputItems()
			itemkt = items.Size() - 1
			#itemkttrial = items.Size() - 1
			#for i in range(5):    # try to ensure that Viewer object creation has caught up
			#	time.sleep(1)
			#	items = desout.GetOutputItems()
			#	itemkt = items.Size() - 1
			#	if itemkt == itemkttrial:   # no new items have arrived
			#		break
			#	else:
			#		itemkttrial = itemkt
			
			while itemkt >= 0 and not tablenum:
				item = items.GetItemAt(itemkt)
				if item.GetType() == SpssClient.OutputItemType.PIVOT:
					if subtype is None or subtype == "".join(item.GetSubType().lower().split()):
						tablenum = itemkt
				itemkt-= 1
		if not tablenum:
			raise ValueError, "No table found to process."

		censorkt = tcensor(items, tablenum, critfield, critvalue, symbol, neighborlist, direction, testtype,
						   appendcaption=appendcaption, othercaption=othercaption, hidecrit=hidecrit)
		return censorkt

def tcensor(objItems, main, critfield='Count', 
			critvalue=5, symbol="", neighborlist=[1], direction='row', testtype='<',
			appendcaption=True,othercaption=None, hidecrit=False):
	"""censor the cells of table main in designated Viewer window."""

	###objItems = desviewer.GetOutputItems()
	main = objItems.GetItemAt(main)
	if main.GetType() != SpssClient.OutputItemType.PIVOT:
		raise ValueError, "A specified item is not a pivot table or does not exist."

	# create criterion function
	try:
		ttype = ['<', '<=','=','==','>','>=','!=', '~='].index(testtype)
		if ttype == 0:
			olist = [True, False, False]
		elif ttype == 1:
			olist = [True, True, False]
		elif ttype == 2 or ttype == 3:
			olist = [False, True, False]
		elif ttype == 4:
			olist = [False, False, True]
		elif ttype == 5:
			olist = [False, True, True]
		elif ttype == 6 or olist == 7:
			olist = [True, False, True]
	except:
		raise ValueError, "Invalid comparison type: " + testtype

	def crittest(value):
		"""return whether value meets the criterion test.

	    Tries to handle locale formatted and decorated strings via floatex function"""

		try:
			c = cmp(abs(floatex(value)), critvalue)
			return olist[c+1]
		except:
			return False

	try:
		PivotTable = main.GetSpecificType()
	except:
		time.sleep(.5)
		PivotTable = other.GetSpecificType()  # give it another chance
	censorkt = 0
	try:
		PivotTable.SetUpdateScreen(False)
		if direction == 'row':
			lblarray = PivotTable.ColumnLabelArray()
		elif direction == 'column':
			lblarray = PivotTable.RowLabelArray()			
		else:
			raise ValueError, "direction must be 'row' or 'column'"
		censorkt = censortbl(lblarray, PivotTable, critfield, crittest, symbol, 
							 neighborlist, direction, hidecrit)
		if appendcaption:
			if othercaption is None:
				othercaption = "Number of values censored because of " + critfield + ": " + unicode(censorkt)
			PivotTable.SetCaptionText(PivotTable.GetCaptionText() + "\n" + othercaption)
		PivotTable.Autofit()
	finally:
		PivotTable.SetUpdateScreen(True)
		return censorkt

def censortbl(labels, PivotTable, critfield, crittest, symbol, neighborlist, direction, hidecrit):
	"""Censor the table, returning the number of values censored.

	labels is the row or column label array where the critfield should be found.
	PivotTable is the table to process.
	crittest is a test function to be used for the comparison.
	symbol is the symbol used to replace the value.
	neighborlist is the list of neighboring cells in which to do the replacement when the test succeeds
	direction is row or col, which determines how to interpret neighborlist.
	hidecrit if True causes the criterion row or column to be hidden."""

	# an empty symbol can cause the DataCellArray to collapse
	if symbol == '':
		symbol = ' '
	try:
		datacells = PivotTable.DataCellArray()
		rows = direction == 'row'
		if rows:
			dimsize = datacells.GetNumColumns()
			otherdimsize = datacells.GetNumRows()
			lbllimit = labels.GetNumRows() - 1
		else:
			dimsize = datacells.GetNumRows()
			otherdimsize = datacells.GetNumColumns()
			lbllimit = labels.GetNumColumns() - 1
		censorkt = 0
		foundcritfield = False
		c = LayerManager(PivotTable)
		for facenumber, face in enumerate(c.layers()):
			for i in range(dimsize):
				a1, a2 = _sargs(rows, lbllimit, i)
				if labels.GetValueAt(a1, a2)  == critfield:
					foundcritfield = True
					for other in range(otherdimsize):
						aa1, aa2 = _sargs(rows, other, i)
						if crittest(datacells.GetValueAt(aa1, aa2)):
							for offset in neighborlist:
								if 0 <= i+ offset < dimsize:
									aaa1, aaa2 = _sargs(rows, other, i + offset)
									datacells.SetValueAt(aaa1, aaa2, symbol)
									datacells.SetHAlignAt(aaa1, aaa2, SpssClient.SpssHAlignTypes.SpssHAlRight)  # right align cell
									censorkt += 1
					if hidecrit and facenumber == 0:   # only need to hide once for all the layers
						hide(labels, rows, i, lbllimit)
	except AttributeError:
		print "Error in censortbl:", sys.exc_info()[0]
		raise
	if not foundcritfield:
		print  "Warning: The criterion field was not found in the table: " + critfield
		raise AttributeError, "The criterion field was not found in the table: " + critfield

	return censorkt

def hide(array, rows, i, lastdim):
	"""Hide the data and labels at i.
	array is the array of row or column labels.
	i is the row or column number to hide.
	lastdim is the index of the innermost label row or column."""

	#collblarray = PivotTable.columnlabelarray()
	#lblnumrows = collblarray.numrows
	x, y = _sargs(rows, lastdim, i)
	array.HideLabelsWithDataAt(x, y)

def _sargs(row,x,y):
	""" return x, y, if row == True else y,x"""
	if row:
		return (x,y)
	else:
		return (y,x)

class LayerManager(object):
	def __init__(self, pt):
		"""pt is an activated pivot table"""
		self.ptmgr = pt.PivotManager()
		self.numlayerdims = self.ptmgr.GetNumLayerDimensions()
		self. layercats = []
		self.layercurrcat = []
		for c in range(self.numlayerdims):
			self.layercats.append(self.ptmgr.GetLayerDimension(c).GetNumCategories())
			self.layercurrcat.append(self.ptmgr.GetLayerDimension(c).GetCurrentCategory())

	def layers(self):
		"""Generator to iterate over all the categories of all the dimensions in the layer.

		Returns the current category number, but the main purpose is to change the current category."""

		if self.numlayerdims == 0:
			yield 0
		else:
			for ld in range(self.numlayerdims):
				cc = self.layercurrcat[ld]
				for c in range(self.layercats[ld]):
					yield cc
					cc = (cc+1) % self.layercats[ld]
					self.ptmgr.LayerDimension(ld).SetCurrentCategory(cc)

# row-oriented merge functions
def makealtrowfunc(label):
	"""make a closure with appropriate attachment label
	
	label is the text for matching.
	A None label will never match, so the entire tuple will always be returned in that case."""
	
	def altrowfunc(tup, othertable):
		if tup[-1] == label:
			if omitstatistics:
				tup = tuple([item for item in tup if item != "Statistics"])
			return tup[0:-1]
		else:
			if omitstatistics:
				tup = tuple([item for item in tup if item != "Statistics"])
			return tup
	return altrowfunc

def altcolfunc(tup, othertable):
	if othertable:
		if omitstatistics:
			tup = tuple([item for item in tup if item != "Statistics"])
		return tup[:-1]
	else:
		if omitstatistics:
			tup = tuple([item for item in tup if item != "Statistics"])
		return tup
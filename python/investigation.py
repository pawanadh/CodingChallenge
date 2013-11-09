import os

folder_data_intermediate = '/data/intermediate'

if not os.path.exists(folder_data_intermediate):
    os.makedirs(folder_data_intermediate)


# ===============================
# STEP 1: Load input data in JSon format:
import json

inputPath = 'data/input/'
listingData = [json.loads(line) for line in open(inputPath + 'listings.txt')]
productData = [json.loads(line) for line in open(inputPath + 'products.txt')]

# Convert input data into Pandas data frames:
from pandas import DataFrame, Series
import pandas as pd
import numpy as np

listings = DataFrame(listingData)
products = DataFrame(productData)

# ======================================================================
# STEP 2: Level 1 filtering: BY MANUFACTURER

# 2.1 Get lists of unique manufacturers in the 2 files (for matching them up):
lManufs = np.sort(listings['manufacturer']).unique()
pManufs = np.sort(products['manufacturer']).unique()
    # Note: inspecting the above will give encoding errors if using an older versions of Pandas. Ensure you have version 0.11 or more recent.

lManufsSeries = Series(lManufs)
pManufsSeries = Series(pManufs)

# pManufsSeries:
# 0               Agfa
# 1              Canon
# 2              Casio
# 3             Contax
# 4              Epson
# 5           Fujifilm
# 6                 HP
# 7              Kodak
# 8     Konica Minolta
# 9            Kyocera
# 10             Leica
# 11             Nikon
# 12           Olympus
# 13         Panasonic
# 14            Pentax
# 15             Ricoh
# 16           Samsung
# 17             Sanyo
# 18             Sigma
# 19              Sony
# 20           Toshiba


# ----------------------------------------------------------------------
# Data discoveries:
#   1. lManufs has far more manufacturers than pManufs, including some bad data which is clear a product not a manufacturer
#   2. Some aren't even camera products (e.g. UBISOFT Assassin's Creed). 
#   3. Others are, but aren't on main list of products e.g. listings[listings['manufacturer'] == u'Roots']
#   4. In some cases, the listing manufacturer is a subsidiary of the products manufacturer e.g. 'Canon Canada' under 'Canon'
#   5. At least one typo: 'Canoon' instead of 'Canon': listings[listings['manufacturer'] == u'Canoon']
#   6. Product manufacturer gotchas to avoid:
#      6.1 Konica Minolta is two words, but it's simpler to match on single words rather than bigrams. 
#          So match on each word, not the combination. This will also catch cases where either word is used alone.
#      6.2 HP could also match Hewlett Packard. But that's two words. So match on "HP" or "Hewlett" or "Packard".
#      6.3 Fujifilm could also match Fuji or "Fuji film". So rather just match on "Fuji" not "Fujifilm"

# ----------------------------------------------------------------------
# 2.2 Generate and clean up manufacturer mappings in products data:
pManufsMapping = DataFrame( 
    { 'pManuf': pManufsSeries, 'Keyword': pManufsSeries.str.lower() } 
) # By default map each word to itself
pManufsMapping['Keyword'][pManufsMapping['pManuf'] == 'Konica Minolta'] = 'konica'
pManufsMapping = pManufsMapping.append( { 'pManuf': 'Konica Minolta', 'Keyword': 'minolta' }, ignore_index = True )
pManufsMapping = pManufsMapping.append( { 'pManuf': 'HP', 'Keyword': 'hewlett' }, ignore_index = True )
pManufsMapping = pManufsMapping.append( { 'pManuf': 'HP', 'Keyword': 'packard' }, ignore_index = True )
pManufsMapping['Keyword'][pManufsMapping['pManuf'] == 'Fujifilm'] = 'fuji'

pManufKeywords = pManufsMapping['Keyword']

# ----------------------------------------------------------------------
# 2.3 Experiment with Levenshtein distances between various similar strings:
from nltk.metrics import *

s1 = 'Canon'
s2 = 'Canoon'
s3 = 'Cannon'
s4 = 'Cannoon'
s5 = 'Cannonn'
s_nikon = 'Nikon'

# Decide on a reasonable Levenshtein distance for matching manufacturer names:
edit_distance(s1, s2) # 1
edit_distance(s1, s3) # 1
edit_distance(s1, s4) # 2
edit_distance(s1, s5) # 2
edit_distance(s1, s_nikon) # 3

# test...
# min_manuf_word_len = 3
#test...
# edit_distance_threshold = 1

# Safest parameters:
edit_distance_threshold = 2
min_manuf_word_len = 4

# ----------------------------------------------------------------------
# 2.4 Match lManufs to pManufs:
# 
# Precedence:
# 1. Exact match on entire string
# 2. Exact match on a single word in the string
# 3. Match contained in a single word in the string
# 4. Sufficiently small Levenshtein distance to a single word in the string
def matchManuf(lManuf):
    splits = lManuf.lower().split()
    for pManufKeyword in pManufKeywords:
        if pManufKeyword in splits:
            return pManufKeyword
    foundPManufs = [ p for s in splits
                       for p in pManufKeywords
                       if s.find(p.lower()) >= 0
                   ]
    if len(foundPManufs) > 0:
        return foundPManufs[0]
    levenshteinPManufs = [ p for s in splits
                             for p in pManufKeywords
                             if len(s) > min_manuf_word_len 
                             and edit_distance(s, p.lower()) <= edit_distance_threshold
                         ]
    if len(levenshteinPManufs) > 0:
        return levenshteinPManufs[0]
    return ''

mapData = { 'lManuf': lManufsSeries,
            'pManufKeyword': lManufsSeries.apply( matchManuf )
          }
lManufMap = DataFrame( mapData )
lManufMap = pd.merge( lManufMap, pManufsMapping, how='left', left_on='pManufKeyword', right_on='Keyword')
del lManufMap['Keyword']
lManufMap['pManuf'] = lManufMap['pManuf'].fillna('')
lManufMap

# ----------------------------------------------------------------------
# 2.5 Output intermediate data to check the accuracy of the manufacturer matching:
# 
#Possible mismatches:
def isPossibleMismatch(row):
    return row['pManuf'] != '' and (row['lManuf'].lower().find(row['pManuf'].lower()) == -1)

possibleMismatches = lManufMap.apply(isPossibleMismatch, axis=1)
# This trick was found at: 
#   http://stackoverflow.com/questions/13331698/how-to-apply-a-function-to-two-columns-of-pandas-dataframe
# An alternate approach would have been to modify matchManuf to also return the type of match, as described here: 
#   http://stackoverflow.com/questions/12356501/pandas-create-two-new-columns-in-a-dataframe-with-values-calculated-from-a-pre?rq=1

lManufMap[lManufMap['pManuf'] == ''].to_csv('data/intermediate/unmatched_manufs.csv', encoding='utf-8')
lManufMap[lManufMap['pManuf'] != ''].to_csv('data/intermediate/matched_manufs.csv', encoding='utf-8')
lManufMap[possibleMismatches].to_csv('data/intermediate/possible_mismatched_manufs.csv', encoding='utf-8')
# ASSUMPTION: using utf-8 encodings will be sufficient. 
# Note that Excel may show some less common letters as a "?". Nut in a text editor they are correct.

lManufMap[possibleMismatches]

#                           lManuf pManufKeyword          pManuf
# 428                   CANAL TOYS         canon           Canon
# 435                       Canoon         canon           Canon
# 439       Midland Consumer Radio         casio           Casio
# 440        Clip Sonic Technology        konica  Konica Minolta
# 441                       Konica        konica  Konica Minolta
# 447                      Epsilon         epson           Epson
# 451                         Fuji          fuji        Fujifilm
# 452                Fuji Film USA          fuji        Fujifilm
# 453                 Fuji FinePix          fuji        Fujifilm
# 454  Fuji Photo Film Europe GmbH          fuji        Fujifilm
# 455    Fuji Photo Film Usa, Inc.          fuji        Fujifilm
# 460              Hewlett Packard       hewlett              HP
# 461         Hewlett Packard GmbH       hewlett              HP
# 464                        LESCA         leica           Leica
# 466                        Leitz         leica           Leica
# 467                        Lenco         leica           Leica
# 469                      Minolta       minolta  Konica Minolta
# 475                      OPYMPUS       olympus         Olympus
# 476                      Olmypus       olympus         Olympus
# 482                     Olymypus       olympus         Olympus
# 498                      SAMYANG       samsung         Samsung
# 521           Syntax Corporation        contax          Contax

# DECISION: Quite a few of the above are mismatches. 
#           However the various olympus mappings and (possibly) canoon are correctly matched.
#           So rather allow all of these through and let the next layer of matching eliminate them.
#           
#           The alternative is to hard-code their elimination.
#           But rather avoid unnecessary customizations.

# DISCOVERIES:
# 1. Inspecting the 3 csv files showed up some anomalies.
#    This led to the new step 2.2 and subsequent refactorings.

# ----------------------------------------------------------------------
# 2.6 Map to manufacturers
# 

listingsByPManufAll = pd.merge( listings, lManufMap, how='inner', left_on='manufacturer', right_on='lManuf')
listingsByPManuf = listingsByPManufAll[listingsByPManufAll['pManuf'] != ''].reindex(columns = ['pManuf','lManuf', 'title','currency','price'])
listingsByPManuf.to_csv('data/intermediate/filtered_listings_by_pmanuf.csv', encoding='utf-8')


# ==============================================================================
# 3. Prepare the listings data for matching to products
# 

# ----------------------------------------------------------------------
# 3.1 Define terms that filter the product info from ancillary info
# 
import re
from string import Template

# Languages found by inspecting csv files: English, French, German...
applicabilitySplitTerms = [ u'for', u'pour', u'f�r', u'fur', u'fuer' ]
additionalSplitTerms = [ 'with',  'w/', 'avec', 'mit', '+' ]

applicabilityPatterns = '|'.join([ re.escape(term) for term in applicabilitySplitTerms ])
additionalPatterns = '|'.join([ re.escape(term) for term in additionalSplitTerms ])
allTermPatterns = applicabilityPatterns + '|' + additionalPatterns

patternToExpand = ur'''
^
\s*
(?P<productDesc>
  (?:
    (?!
      (?<!\w)
      (?:$allTermPatterns)
      (?!\w)
    )
    .
  )+
  # Ensure the last character is non-whitespace:
  (?:
    (?!
      (?<!\w)
      (?:$allTermPatterns)
      (?!\w)
    )
    \S
  )
)
\s*
(?:
  (?P<extraProdDetailsSection>
    (?:
      (?:$allTermPatterns)
      \W*
    )
    (?P<extraProdDetails>
      .+
      \S # Ensure the last character is non-whitespace:
    )
  )
  \s*
)?
$$
'''

patternTemplate = Template(patternToExpand)
titleSplitRegexPattern = patternTemplate.substitute(allTermPatterns=allTermPatterns)
titleSplitRegex = re.compile( titleSplitRegexPattern, re.IGNORECASE | re.UNICODE | re.VERBOSE )

#testing regex matches...
regexTestString = '   Nikon EN-EL9a 1080mAh Ultra High Capacity Li-ion Battery Pack   for Nikon D40, D40x, D60, D3000, & D5000 Digital SLR Cameras with love  for ever   with   salt and pepper'
testMatch = titleSplitRegex.match(regexTestString)
if testMatch:
  testMatch.group('productDesc')
  testMatch.group('extraProdDetails')
  # Discovery: Python provides no way to access all the captures for a named capture group if there is more than one (e.g. the text "for" is repeated)
  # Action: Simplify the regex to have a named captured group for extraProdDetails, instead of multiple ones

  
# ----------------------------------------------------------------------
# 3.2 Split the product titles into a product description and ancillary information
# 

def splitTitle(title):
    titleMatch = titleSplitRegex.match(title)
    return titleMatch.group('productDesc'), titleMatch.group('extraProdDetails')

title_regex_pairs = listingsByPManuf['title'].apply(splitTitle)
productDescs, extraProdDetails = zip(* title_regex_pairs )
listingsByPManuf['productDesc'] = productDescs
listingsByPManuf['extraProdDetails'] = extraProdDetails

listingsByPManuf.to_csv('data/intermediate/filtered_by_pmanuf_with_split_title.csv', encoding='utf-8')

# Check that the following give empty data frames:
# listingsByPManuf[pd.isnull(listingsByPManuf['productDesc'])]
# listingsByPManuf[listingsByPManuf['productDesc'] == '']

  
# ----------------------------------------------------------------------
# 3.3 Group by the product descriptions to reduce the amount of matching required
# 

productDescGrouping = listingsByPManuf.groupby(['pManuf', 'productDesc'])


# ==============================================================================
# 4. Prepare the products for matching to listings by finding duplicates:
# 

# ----------------------------------------------------------------------
# 4.1 Find duplicate models:
prod_model_counts = products.model.value_counts()
dup_models = prod_model_counts[prod_model_counts > 1]
#                     announced-date      family manufacturer   model
# 226  2011-02-15T19:00:00.000-05:00  Cybershot          Sony    T110
# 257  2009-02-16T19:00:00.000-05:00         NaN      Samsung   SL202
# 288  2011-02-15T19:00:00.000-05:00     FinePix     Fujifilm   S4000
# 370  2011-02-06T19:00:00.000-05:00        ELPH        Canon  300 HS
# 510  1998-11-01T19:00:00.000-05:00         NaN      Olympus   C900Z
# 517  1998-02-02T19:00:00.000-05:00     FinePix     Fujifilm     700
# 653  1999-04-15T20:00:00.000-04:00     PhotoPC        Epson     800
# 711  1998-03-15T19:00:00.000-05:00     Coolpix        Nikon     600
# 718  1999-02-14T19:00:00.000-05:00     Coolpix        Nikon     700
# 722  1996-05-12T20:00:00.000-04:00   PowerShot        Canon     600

# ------------------------------------------
# 4.2 Find duplicates by manufacturer and model:

products[products.duplicated(['manufacturer', 'model'])]
#                     announced-date family manufacturer   model
# 257  2009-02-16T19:00:00.000-05:00    NaN      Samsung   SL202
# 370  2011-02-06T19:00:00.000-05:00   ELPH        Canon  300 HS

# The problem with duplicated() is that it omits the first duplicate found.
# The following code allows us to examine the 'family' values for all records:
manuf_model_groups = products.groupby(['manufacturer', 'model'])
manuf_model_group_sizes = manuf_model_groups.size()
manuf_model_sizes = DataFrame({'group_count' : manuf_model_group_sizes}).reset_index()
manuf_model_dup_groups = manuf_model_sizes[manuf_model_sizes.group_count > 1]
manuf_model_dups = pd.merge(products, manuf_model_dup_groups, on=['manufacturer','model'], sort=True)[['manufacturer','family','model','announced-date']]
manuf_model_dups
#   manufacturer family   model                 announced-date
# 0        Canon   IXUS  300 HS  2010-05-10T20:00:00.000-04:00
# 1        Canon   ELPH  300 HS  2011-02-06T19:00:00.000-05:00
# 2      Samsung    NaN   SL202  2009-02-16T19:00:00.000-05:00
# 3      Samsung    NaN   SL202  2009-02-16T19:00:00.000-05:00


# ----------------------------------------------------------------------
# 4.3 Set the required matching action on the duplicates:
# 
# Note: A new text column named 'matchRule' will be added to the data frame.
#       Its value will guide the behaviour of the matching algorithm.
# 

# Ignore products which match on all 3 fields: manufacturer, family and model
manFamModel_dups = DataFrame({'isDup': products.duplicated(['manufacturer', 'family', 'model'])})
manFamModel_dups['matchRule'] = ''
manFamModel_dups.matchRule[manFamModel_dups.isDup] = 'ignore'

products['matchRule'] = manFamModel_dups.matchRule[manFamModel_dups.isDup]

# Match on family and model if the manufacturer and model are duplicated (but not the family):
manuf_model_groups = products[products.matchRule.isnull()].groupby(['manufacturer', 'model'])
manuf_model_group_sizes = manuf_model_groups.size()
manuf_model_sizes = DataFrame({'group_count' : manuf_model_group_sizes}).reset_index()  # reset_index() will copy the index into a column named 'index'
manuf_model_dup_groups = manuf_model_sizes[manuf_model_sizes.group_count > 1]

products2 = products.reset_index()  
    # products2 now has its index copied to a column named 'index'
    # This will be useful for matching up to the original index after the merge below...
manuf_model_dups = pd.merge(products2, manuf_model_dup_groups, on=['manufacturer','model'], sort=True).set_index('index')[['manufacturer','family','model']]
manuf_model_dups['matchRule'] = 'familyAndModel'
products = products.combine_first(manuf_model_dups[['matchRule']])  
    # Note: combine_first() is like a vectorized coalesce.
    #       It matches rows based on index.
    #       For each row and each column it takes the first non-null value
    #       in the two data frames (products and manuf_model_dups).

# test: products[products.matchRule.notnull()]


# ==============================================================================
# 5. Analyze the model column in the products data set in preparation 
#    for setting up rules for matching listings to products
# 

# ----------------------------------------------------------------------
# 5.1 Set up test regex for splitting the model into an array
#     of alphanumeric and non-alphanumeric sections
# 

regexTestString = ':::aaa-bb def   ghi   '

# Following regex pattern works to split with .Net, but not Python:
alphaNumSplitRegexPattern = r'(?<!^)\b'
alphaNumSplitRegex = re.compile( alphaNumSplitRegexPattern, re.IGNORECASE | re.UNICODE | re.VERBOSE )
alphaNumSplitRegex.split(regexTestString)

# This doesn't work either:
alphaNumSplitRegexPattern = '\b'
alphaNumSplitRegex = re.compile( alphaNumSplitRegexPattern, re.IGNORECASE | re.UNICODE | re.VERBOSE )
alphaNumSplitRegex.split(regexTestString)

# This also only works with .Net (\b seems to work differently)...
alphaNumRegexPattern = '(?:^|\b)(?:\w+|\W+)'
alphaNumRegex = re.compile( alphaNumRegexPattern, re.IGNORECASE | re.UNICODE | re.VERBOSE )
alphaNumRegex.findall(regexTestString)

# This works:
alphaNumRegexPattern = '(?:\w+|\W+)'
alphaNumRegex = re.compile( alphaNumRegexPattern, re.IGNORECASE | re.UNICODE | re.VERBOSE )
alphaNumRegex.findall(regexTestString)
alphaNumRegex.findall('aaa-bbb-ccc::ddd   ')
alphaNumRegex.findall('    aaa-bbb-ccc::ddd   ')

# Improve this to differentiate alphabetic blocks from numeric blocks as well
alphaNumRegexPattern = '(?:[A-Za-z]+|\d+|\W+)'
alphaNumRegex = re.compile( alphaNumRegexPattern, re.IGNORECASE | re.UNICODE | re.VERBOSE )
alphaNumRegex.findall(regexTestString)
alphaNumRegex.findall('aaa15-10bbb-ccc::ddd   ')
alphaNumRegex.findall('    aaa-bbb-ccc::ddd   ')


def split_into_blocks_by_alpha_num(stringToSplit):
    return alphaNumRegex.findall(stringToSplit)


# ----------------------------------------------------------------------
# 5.2 Categorize each block into one of the following:
#     c = consonants only
#     a = alphabetic only
#     n = numeric only
#     _ = white space (1 or more i.e. \s+)
#     - = a dash only, since this is likely to be a common character in product codes
#     ~ = a dash preceded or succeeded by whitespace characters
#     ( = a left bracket, possibly with whitespace on either side
#     ) = a right bracket, possibly with whitespace on either side
#     ! = a division symbol (/), possibly with whitespace on either side
#         Note: an exclamation mark is used since this character can be part of a file name
#     . = a single dot (no white space)
#     x = any other non-alphanumeric sequences
#
# SUBSEQUENTLY REMOVED: 
#     w = a combination of alphabetic and numeric characters
#

# Use a list of tuples (instead of a dictionary) to control order of checking (dictionaries are unordered):
blockClassifications = [
        ('c', r'^[B-DF-HJ-NP-TV-XZb-df-hj-np-tv-xz]+$'),
        ('a', r'^[A-Za-z]+$'),
        ('n', r'^\d+$'),
        ('_', r'^\s+$'),
        ('-', r'^\-$'),
        ('~', r'^\s*\-\s*$'),  # Allow spaces on either side of the dash
        ('(', r'^\s*\(\s*$'),  # To cater for "GXR (A12)"
        (')', r'^\s*\)\s*$'),  # To cater for "GXR (A12)"
        ('!', r'^\s*\/\s*$'),  # To cater for "DSC-V100 / X100"
        ('.', r'^\.$'),  # To cater for "4.3"
        ('x', r'^.+$')
    ]
    # A potential issue here is that the regex patterns assume ANSI characters.
    # However it seems that all the products listed are English, so this shouldn't matter.
    # Some of the listings are in other languages though, so 
    
blockClassificationRegexes = [(classifier, re.compile(pattern, re.IGNORECASE | re.UNICODE | re.VERBOSE )) for (classifier,pattern) in blockClassifications]

def derive_classification(blockToClassify):
    for (classifier, regex) in blockClassificationRegexes:
        if regex.match(blockToClassify):
            return classifier
    return '$'

# Test classification function
# 
# Note: These should be moved into a unit test class 
#       when converting this exploratory script into an application
# 
def test_classification(blockToClassify, expected):
    classification = derive_classification(blockToClassify)
    if classification != expected:
        print '"{0}" classified as "{1}". But "{2}" expected!'.format(blockToClassify, classification, expected)

#Expect following to fail (test that test_classification works properly):
test_classification('abcd', 'test_failure')

# Expect these to succeed:
test_classification('abcd', 'a')
test_classification('1234', 'n')
test_classification('bcd', 'c')
test_classification(' \t ', '_')
test_classification('-', '-')
test_classification('   -  ', '~')
test_classification(':', 'x')
test_classification(':-)', 'x')
test_classification('', '$')
test_classification('.', '.')
test_classification('/', '!')
test_classification('  /  ', '!')
test_classification('(', '(')
test_classification('  (  ', '(')
test_classification('  )  ', ')')

# ----------------------------------------------------------------------
# 5.3 Categorize a list of blocks into a 
#     single concatenated string of classifications:
#

def derive_classifications(blocksToClassify):
    block_classifications = [derive_classification(block) for block in blocksToClassify]
    classification = ''.join(block_classifications)
    # There is no need to differentiate consonant blocks from other alphabetic blocks 
    # if a dash or number precedes or succeeds the consonant block 
    # (since that already indicates a product code pattern)...
    classification = re.sub(r'(?<=\-|n)c', 'a', classification)
    classification = re.sub(r'c(?=\-|n)', 'a', classification)
    return classification

def test_derive_classifications(blocksToClassify, expected):
    classification = derive_classifications(blocksToClassify)
    if classification != expected:
        print '"{0}" classified as "{1}". But "{2}" expected!'.format(','.join(blocksToClassify), classification, expected)

# test that test_derive_classifications works by giving an incorrect expectation:
test_derive_classifications(['abc','12','-','abc',':','12', '  ','MP'], 'test_failure')

# Expect these to succeed:
test_derive_classifications(['abc', '12','-','abc',':','12', '  ','MP'], 'an-axn_c')
test_derive_classifications(['  :  ','  -  ','12','.','1','MP', '','IS'], 'x~n.na$a')
test_derive_classifications([],'')
test_derive_classifications(['jklmn'],'c')
test_derive_classifications(['jklmn',' '],'c_')
test_derive_classifications(['jklmn','15'],'an')
test_derive_classifications(['15', 'jklmn'],'na')

# ----------------------------------------------------------------------
# 5.4 Convert a string into a list of tuples, where each tuple contains:
#     a. A list of the various alphanumeric and non-alphanumeric blocks
#     b. The classification string for the list of blocks
#

def get_blocks_and_classification_tuple(text_to_classify):
    blocks = split_into_blocks_by_alpha_num(text_to_classify)
    classification = derive_classifications(blocks)
    return blocks, classification

model_block_pairs = products['model'].apply(get_blocks_and_classification_tuple)
model_blocks, model_classifications = zip(* model_block_pairs )
products['model_blocks'] = model_blocks
products['model_classification'] = model_classifications

# See how many patterns there are:
# 
# Quick way...
# products.model_classification.value_counts()
# 
# Better way (can get examples too)...

def group_and_save_classification_patterns(source_column, classification_column, columns_to_export, classification_folder):
  classification_patterns = products.groupby(classification_column)
  classification_record_counts = products[classification_column].value_counts()
  #Ensure the folder path exists:   
  pattern_folder_path = r'data/intermediate/' + classification_folder
  if not os.path.exists(pattern_folder_path):
      os.makedirs(pattern_folder_path)
  # Save a csv file per pattern, and write a summary record to the console:
  for pattern, group in classification_patterns:
      example = group.iloc[0][source_column]
      record_count = classification_record_counts[pattern]
      print 'Pattern: {0:<15} count: {1:<6} example: {2}'.format(pattern, record_count, example)
      # Write to an intermediate file for further investigation:
      pattern_file_path = r'{0}/{1}.csv'.format(pattern_folder_path, pattern)
      group[columns_to_export].to_csv(pattern_file_path, encoding='utf-8')

group_and_save_classification_patterns('model', 'model_classification', ['manufacturer','family','model','model_classification','model_blocks'], 'model_classifications')

# Original classification patterns found in 'model' column BEFORE REFACTORING:
# 
# Pattern: a             count: 4     example: Digilux
# Pattern: a-a           count: 2     example: K-r
# Pattern: a-a_n         count: 2     example: V-LUX 20
# Pattern: a-n           count: 56    example: NEX-3
# Pattern: a-n_a         count: 20    example: C-2500 L
# Pattern: a-w           count: 198   example: DSC-W310
# Pattern: a-w_a_a       count: 1     example: EOS-1D Mark IV
# Pattern: a-wxw         count: 1     example: DSC-V100 / X100
# Pattern: a_a           count: 1     example: N Digital
# Pattern: a_a-w         count: 5     example: PEN E-P2
# Pattern: a_a_a         count: 1     example: GR Digital III
# Pattern: a_a_n         count: 7     example: mju Tough 8010
# Pattern: a_a_w         count: 1     example: Kiss Digital X3
# Pattern: a_n           count: 12    example: mju 9010
# Pattern: a_n_a         count: 2     example: EX 1500 Zoom
# Pattern: a_w           count: 4     example: Mini M200
# Pattern: axwx          count: 1     example: GXR (A12)
# Pattern: n             count: 36    example: 1500
# Pattern: n_a           count: 24    example: 130 IS
# Pattern: nxn           count: 1     example: 4.3
# Pattern: w             count: 329   example: TL240
# Pattern: w_a           count: 34    example: SD980 IS
# Pattern: w_ax          count: 1     example: CL30 Clik!
# 

# ----------------------------------------------------------------------
# Notes based on above matches:
# 
# 1. At this point there are only 4 patterns (with 1 record each) using the unmatched 'x' characters.
#    These could just be ignored. However there is a risk, because we don't know how how many matching *listings* there might be.
#    Alternatively, 3 of these can be handled by adding support for: /.()
#    Adding custom support for the '!' in "CL30 Clik!" doesn't seem worth it, and the CL30 product code might be good enough.
# 
# 2. There are 329 'w' patterns which are pieces of text with both alphabetic and numberic characters.
#    These are likely to all be product codes.. Consider the example: "TL240".
#    It would be better to match this on all of: "TL240", "TL-240", "TL 240".
#    So rather remove the 'w' block and always differentiate alphabetic from numeric.
# 
# 3. Consider the GXR. This consists only of consonants, indicating that it is also a product code.
#    So add a new match on words that are all consonants.
#    
#    But bear in mind the following:
#    
#    a. Consonant blocks that are preceded or succeeded by a dash or number, are clearly product codes because of the dash / number.
#       So 'normalize' classification codes by replacing 'c' codes with 'a' codes if preceded or succeeded by a dash or number.
#       This will reduce the total number of classification patterns to deal with.
#
#    b. They may not be product codes. They could also be domain-specific abbreviations or units of measure.
#       For example, "MP" for mega-pixels.
#       
#       Let's list all the consonant blocks first to see if this is really an issue.
#       If it is a problem, then only add a list of all consonant strings to convert to 'a' classifications.
#
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# Classification patterns found in 'model' column after refactoring:
# 
# Pattern: a               count: 4      example: Digilux
# Pattern: a-a             count: 2      example: K-r
# Pattern: a-a_n           count: 2      example: V-LUX 20
# Pattern: a-an            count: 167    example: DSC-W310
# Pattern: a-an!an         count: 1      example: DSC-V100 / X100
# Pattern: a-ana           count: 10     example: DSC-HX100v
# Pattern: a-n             count: 56     example: NEX-3
# Pattern: a-n_a           count: 17     example: C-2000 Zoom
# Pattern: a-n_c           count: 3      example: C-2500 L
# Pattern: a-na            count: 21     example: QV-5000SX
# Pattern: a-na_a_a        count: 1      example: EOS-1D Mark IV
# Pattern: a_a-an          count: 4      example: PEN E-P2
# Pattern: a_a-ana         count: 1      example: PEN E-PL1s
# Pattern: a_a_an          count: 1      example: Kiss Digital X3
# Pattern: a_a_n           count: 7      example: mju Tough 8010
# Pattern: a_an            count: 3      example: Mini M200
# Pattern: a_n             count: 12     example: mju 9010
# Pattern: a_n_a           count: 2      example: EX 1500 Zoom
# Pattern: a_na            count: 1      example: mju 550WP
# Pattern: an              count: 277    example: TL240
# Pattern: an_a            count: 31     example: SD980 IS
# Pattern: an_ax           count: 1      example: CL30 Clik!
# Pattern: an_c            count: 3      example: SX220 HS
# Pattern: ana             count: 37     example: Z900EXR
# Pattern: c(an)           count: 1      example: GXR (A12)
# Pattern: c_a             count: 1      example: N Digital
# Pattern: c_a_a           count: 1      example: GR Digital III
# Pattern: n               count: 36     example: 1500
# Pattern: n.n             count: 1      example: 4.3
# Pattern: n_a             count: 16     example: 130 IS
# Pattern: n_c             count: 8      example: 310 HS
# Pattern: na              count: 15     example: 900S
#
# Note: 32 classification patterns after the refactoring, compared to 23 before. So not untractable.
#



# ==============================================================================
# 6. Analyze the family column in the products data set
#    to decide how to combine it with the model search patterns:
# 

# ----------------------------------------------------------------------
# 6.1 See how much variability there is in the family column:
# 

products.family.fillna('').value_counts().sort_index()

#                 258
# Alpha            13
# Coolpix          43
# Cyber-shot       42
# Cybershot         8
# Cybershot         6
# D-LUX             1
# DiMAGE            4
# Digilux           2
# Digital IXUS      9
# ELPH              3
# EOS               8
# EasyShare        24
# Easyshare         2
# Exilim           30
# FinePix          85
# Finecam           1
# Finepix           1
# IXUS              5
# IXY               5
# Lumix            80
# Mavica           10
# Optio            16
# PhotoPC           9
# Photosmart        7
# PowerShot        46
# Rebel             4
# Stylus           14
# Tough             1
# ePhoto            6

# Notes based on above:
# 
# 1. Some duplication:
#       a. Cybershot, "Cybershot ", Cyber-shot
#            TIP: above diagnosed using... products[products.family.str.startswith('Cyber').fillna(False)]
#       b. Digital IXUS, IXUS
#       c. EasyShare, Easyshare
#       d. FinePix, Finepix
# 
# 2. Many records don't have a family. Of the remainder, all are pure alphabetic, except for:
#       a. A space to be trimmed from " Cybershot"
#       b. A dash in Cyber-shot and D-Lux
#       c. A space in "Digital IXUS"
# 
# Conclusions: 
# 
# 1. The data looks cleaner than expected.
#    Even the extra dash in Cyber-shot shouldn't matter, as 
#    the pattern matching regex will probably treat the dash as optional anyway.
# 
# 2. The classification patterns will be fairly uniform.
#    So a composite classification code comprising family and model may be tractable.
#    So there is merit in investigating this.
#    
# 3. The benefit of doing so, is that there are 36 model records which are purely numeric.
#    The family column will be needed to avoid spurious matches.
# 
# 4. To think about... 
#    Can the family and model simply be concatenated (with a space between them)?
#    Or should there be a special separate character? e.g. '+'
#


# ----------------------------------------------------------------------
# 6.2 Perform the classification on the family column:
# 

family_block_pairs = products['family'].fillna('').apply(get_blocks_and_classification_tuple)
family_blocks, family_classifications = zip(* family_block_pairs )
products['family_blocks'] = family_blocks
products['family_classification'] = family_classifications

# check:
products.family_classification.value_counts()

# a      427
#        258
# a-a     43
# a_a      9
# a_       6


# ----------------------------------------------------------------------
# 6.3 Create a composite classification:
# 

products['family_and_model'] = products.family.fillna('') + ' + ' + products.model.fillna('')
products['composite_classification'] = products.family_classification + '+' + products.model_classification

group_and_save_classification_patterns('family_and_model', 'composite_classification', ['manufacturer','family','model','composite_classification','family_blocks','model_blocks'], 'composite_classifications')

# All composite classifications:
# 
# Pattern: +a              count: 2      example:  + Digilux
# Pattern: +a-a            count: 2      example:  + K-r
# Pattern: +a-a_n          count: 2      example:  + V-LUX 20
# Pattern: +a-an           count: 11     example:  + PDR-M60
# Pattern: +a-an!an        count: 1      example:  + DSC-V100 / X100
# Pattern: +a-ana          count: 2      example:  + R-D1x
# Pattern: +a-n            count: 41     example:  + FE-5010
# Pattern: +a-n_a          count: 17     example:  + C-2000 Zoom
# Pattern: +a-n_c          count: 2      example:  + C-2500 L
# Pattern: +a-na           count: 21     example:  + QV-5000SX
# Pattern: +a-na_a_a       count: 1      example:  + EOS-1D Mark IV
# Pattern: +a_a-an         count: 4      example:  + PEN E-P2
# Pattern: +a_a-ana        count: 1      example:  + PEN E-PL1s
# Pattern: +a_a_n          count: 7      example:  + mju Tough 8010
# Pattern: +a_an           count: 1      example:  + Kiss X4
# Pattern: +a_n            count: 7      example:  + mju 9010
# Pattern: +a_na           count: 1      example:  + mju 550WP
# Pattern: +an             count: 112    example:  + TL240
# Pattern: +an_a           count: 2      example:  + DC200 plus
# Pattern: +an_c           count: 1      example:  + X560 WP
# Pattern: +ana            count: 17     example:  + HZ15W
# Pattern: +c(an)          count: 1      example:  + GXR (A12)
# Pattern: +c_a            count: 1      example:  + N Digital
# Pattern: +c_a_a          count: 1      example:  + GR Digital III
# Pattern: a+a             count: 2      example: Digilux + Zoom
# Pattern: a+a-an          count: 119    example: Exilim + EX-Z29
# Pattern: a+a-ana         count: 3      example: Cybershot + DSC-HX100v
# Pattern: a+a-n           count: 15     example: Alpha + NEX-3
# Pattern: a+a-n_c         count: 1      example: Optio + WG-1 GPS
# Pattern: a+a_a_an        count: 1      example: EOS + Kiss Digital X3
# Pattern: a+a_an          count: 2      example: EasyShare + Mini M200
# Pattern: a+a_n           count: 5      example: Stylus + Tough 6000
# Pattern: a+a_n_a         count: 2      example: DiMAGE + EX 1500 Zoom
# Pattern: a+an            count: 159    example: Coolpix + S6100
# Pattern: a+an_a          count: 29     example: PowerShot + SD980 IS
# Pattern: a+an_ax         count: 1      example: ePhoto + CL30 Clik!
# Pattern: a+an_c          count: 2      example: PowerShot + SX220 HS
# Pattern: a+ana           count: 20     example: Finepix + Z900EXR
# Pattern: a+n             count: 35     example: FinePix + 1500
# Pattern: a+n.n           count: 1      example: Digilux + 4.3
# Pattern: a+n_a           count: 8      example: FinePix + 4700 Zoom
# Pattern: a+n_c           count: 7      example: IXUS + 310 HS
# Pattern: a+na            count: 15     example: Coolpix + 900S
# Pattern: a-a+a-an        count: 37     example: Cyber-shot + DSC-W310
# Pattern: a-a+a-ana       count: 5      example: Cyber-shot + DSC-HX7v
# Pattern: a-a+n           count: 1      example: D-LUX + 5
# Pattern: a_+an           count: 6      example: Cybershot  + W580
# Pattern: a_a+n_a         count: 8      example: Digital IXUS + 130 IS
# Pattern: a_a+n_c         count: 1      example: Digital IXUS + 1000 HS
# 
# Note: Now we're at 49 classification patterns (up from 32).
# 



# ==============================================================================
# 7. Design matching rules based on the classification patterns:
# 
# Goal: 
# -----
# 
# Create a small set of rules that can be used to match these 49 patterns 
#       (and others that could arise with a different data set).
# ______________________________________________________________________________
# 
# Envisioned approach: 
# --------------------
# 
#   1. Create a number of matching regular expressions, 
#      with a numerical value for each, based on the value of that match.
#      
#   2. Some patterns are alternatives to each other, with the highest value being chosen:
#      e.g. match on family + model
#               then model only
#               then exact product code only
#               then alternative product code with optional dashes or spaces between parts of the code
#               then a product code and the next word 
#                   (so that 130IS can be matched as well as "130 IS").
#               then a product code and the first character of the next word 
#                   (so that "4700z" can be matched as well as "4700 Zoom").
#      
#   3. Others are additive
#      e.g. value of product code
#         + value/s of finding other words in the title (such as IS or Zoom or the Family)
#      
#      NB: A complication here is that the additive value will only be applicable 
#          for some of the previous patterns.
#      
#   4. For each listing:
#        For each product (filtered by the listing's manufacturer):
#          Calculate the highest value match (if any)
#            Notes:
#                i. A threshold can be chosen with values below the threshold being ignored.
#               ii. Match against the listing's productDesc first, 
#                   then against extraProdDetails (with very low value)
#        Sort the list matching products
#        If exactly one match, or one match that is sufficiently above the rest, make this the final match.
#        Otherwise, if there are multiple matches, flag for further investigation (to identify possible new rules).
#        
#   5. Use flagged listings to generate new matching rules. 
#      Repeat this process until further improvement is either not possible or not desirable.
#      
#   6. Invert the relationship between listings and chosen products.
#        Group listings by the chosen products for each listing.
#        Add a listings columns to the products data frame and populate it from the grouped data.
#      
#   7. Output the list of products with their listings.
# ______________________________________________________________________________
# 
# Reality check:
# --------------
# 
# But first...
# 1. Is this the right approach? 
# 2. Are there reasons why it won't work?
# 3. Is there a way to test the approach cheaply?
# 4. Is there a simpler way?
#    e.g. match on product code only
# 5. Is Python the best way to build the rules engine?
# 6. Would a functional language work better?
#    (e.g. due to the pattern matching capabilities, or through using a parser-combinator library)
# 

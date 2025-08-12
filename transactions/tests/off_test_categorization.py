# transactions/tests/test_categorization.py
import logging
from django.test import TestCase
from transactions.categorization import (
    extract_merchant_from_description,
    categorize_transaction,
    suggest_subcategory
)

logger = logging.getLogger(__name__)

class CategorizationTests(TestCase):
    def test_extract_merchant_basic_cleanup(self):
        raw = "PAYMENT TO AMAZON.COM 123456789"
        result = extract_merchant_from_description(raw)
        self.assertEqual(result, "amazon")

    def test_extract_merchant_removes_ids(self):
        raw = "ZELLE FROM JOHN DOE WEB ID:  987654321"
        result = extract_merchant_from_description(raw)
        self.assertNotIn("987654321", result)
        self.assertIn("ZELLE", result)

    def test_categorize_transaction_income(self):
        desc = "DIRECT DEPOSIT PAYROLL"
        amount = 3000.00
        category, subcategory = categorize_transaction(desc, amount)
        self.assertEqual(category, "Income")
        self.assertEqual(subcategory, "Work")

    def test_categorize_transaction_shopping(self):
        desc = "TARGET #12345 ONLINE PURCHASE"
        category, subcategory = categorize_transaction(desc, -50.75)
        logger.debug(f"Category:  {category}, Subcategory:  {subcategory}")
        self.assertEqual(category, "Shopping")
        self.assertEqual(subcategory, "Target")

    def test_categorize_transaction_unknown(self):
        desc = "Random Description Not Matched"
        category, subcategory = categorize_transaction(desc, -22.00)
        self.assertEqual(category, "Uncategorized")
        self.assertEqual(subcategory, "")

    def test_suggest_subcategory_match(self):
        desc = "Dinner at McDonald's"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_suggest_subcategory_no_match(self):
        desc = "XYZ Unknown Vendor"
        result = suggest_subcategory(desc)
        self.assertIsNone(result)

    def test_53MORTGAGELNPAYMENTPPDID1310281170(self):
        desc = "5/3 MORTGAGE LN  PAYMENT                    PPD ID:  1310281170"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_AAAACGNE0069EFTRCC(self):
        desc = "AAA ACG NE0069 EFT RCC"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_ABERCROMBIEANDFITCH(self):
        desc = "ABERCROMBIE AND FITCH"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_ACHDEPOSITINTERNETTRANSFERFROMACCOUNTENDINGIN3607(self):
        desc = "ACH DEPOSIT INTERNET TRANSFER FROM ACCOUNT ENDING IN 3607"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_ACTGlenEllynPrkDst(self):
        desc = "ACT*Glen Ellyn Prk Dst"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_ADELLESFINEAMERICANFO(self):
        desc = "ADELLES FINE AMERICAN FO"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_ALDI40009GLENELLYN(self):
        desc = "ALDI 40009 GLEN ELLYN"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_Amazoncom2I0KQ6F23(self): 
        desc = "Amazon.com*2I0KQ6F23"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_Amazoncom362BW3H63(self): 
        desc = "Amazon.com*362BW3H63"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_AmazonFreshZC9N09BF2(self): 
        desc = "Amazon Fresh*ZC9N09BF2"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_AMAZONMKTPL2Y6PF5O93(self): 
        desc = "AMAZON MKTPL*2Y6PF5O93"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_AMAZONMKTPL5G7WM8BQ3(self): 
        desc = "AMAZON MKTPL*5G7WM8BQ3"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_AMAZONMKTPLACEPMTS(self): 
        desc = "AMAZON MKTPLACE PMTS"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_AMAZONMKTPLVC6LY4R83(self): 
        desc = "AMAZON MKTPL*VC6LY4R83"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_AMAZONPRIMEVO93N0O83(self): 
        desc = "AMAZON PRIME*VO93N0O83"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_AMAZONPRIMEZC0OE4K70(self): 
        desc = "AMAZON PRIME*ZC0OE4K70"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_ANNUALMEMBERSHIPFEE(self): 
        desc = "ANNUAL MEMBERSHIP FEE"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_APPLECARDGSBANKPAYMENT10818648WEBID9999999999(self):
        desc = "APPLECARD GSBANK PAYMENT    10818648        WEB ID:  9999999999"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_APPLECOMBILLONEAPPLEPARKCUPERTINO95014CAUSA(self):
        desc = "APPLE.COM/BILL ONE APPLE PARK CUPERTINO 95014 CA USA"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_APPLECOMBILLONEAPPLEPARKWAY866712775395014CAUSA(self): 
        desc = "APPLE.COM/BILL ONE APPLE PARK WAY 866-712-7753 95014 CA USA"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_APPLEONLINESTORECUPERTINOCA(self):
        desc = "APPLE ONLINE STORE CUPERTINO CA"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_ATMDEBIT727ROOSEVELTRDGLENELLYNIL(self):
        desc = "ATM DEBIT  727 ROOSEVELT RD GLEN ELLYN IL"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_ATMWITHDRAWAL0070900224727ROOSE(self): 
        desc = "ATM WITHDRAWAL                       007090  02/24727 ROOSE"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_ATMWITHDRAWAL0090880128727ROOSE(self):
        desc = "ATM WITHDRAWAL                       009088  01/28727 ROOSE"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_ATMWITHDRAWAL0098090306727ROOSE(self):
        desc = "ATM WITHDRAWAL                       009809  03/06727 ROOSE"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_AURORASTOLPPARKGARAGE(self):
        desc = "AURORASTOLPPARKGARAGE"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_AUTOMATICPAYMENTTHANK(self):
        desc  = "AUTOMATIC PAYMENT - THANK"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_BINNYSBEVERAGEDEPOT021(self):
        desc  = "BINNYS BEVERAGE DEPOT 021"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "alcohol")

    def test_BURSTORALCARE(self):
        desc  = "BURST ORAL CARE"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "dental")

    def test_BUTCHERampBURGERT5EA(self):
        desc  = "BUTCHER &amp; BURGER T5 EA"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_CASEYS6446(self):
        desc  = "CASEYS #6446"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "gas")

    def test_CHASECREDITCRDAUTOPAYPPDID4760039224(self):
        desc  = "CHASE CREDIT CRD AUTOPAY                    PPD ID:  4760039224"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "transfer")

    def test_CHECK4643(self):
        desc  = "CHECK 4643  "
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_CHECK4644(self):
        desc  = "CHECK 4644  "
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_CHECK4660(self):
        desc  = "CHECK 4660  "
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_CHECK4663(self):
        desc  = "CHECK 4663  "
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_CHECK4664STATEFARMRO08PYMTARCID9000313003(self):
        desc  = "CHECK # 4664      STATE FARM RO 08  PYMT             ARC ID:  9000313003  "
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Auto Insurance")

    def test_CHECK4665(self):
        desc  = "CHECK 4665  "
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_CLUBARCADAINC(self):
        desc  = "CLUB ARCADA  INC."
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Entertainment")

    def test_ComEdPAYMENTSPPDID2360938600(self):
        desc  = "ComEd            PAYMENTS                   PPD ID:  2360938600"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Bills & Utilities")

    def test_COSTCOGAS0371(self):
        desc  = "COSTCO GAS #0371"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Gas")

    def test_COSTCOWHSE0371(self):
        desc  = "COSTCO WHSE #0371"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Groceries")

    def test_CSLEYEGC(self):
        desc  = "CS *LEYE GC"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_CULVERSOFWARSAW2(self):
        desc  = "CULVERS OF WARSAW 2"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_DDDOORDASHWINGSTOP(self):
        desc  = "DD *DOORDASH WINGSTOP"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_DicksSportingGoodscom(self):
        desc  = "DicksSportingGoods.com"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_DWELLSOCIALINC(self):
        desc  = "DWELLSOCIAL  INC"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_FIVE0FOURKITCHEN(self):
        desc  = "FIVE 0 FOUR KITCHEN"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_FRESHTHYME108(self):
        desc  = "FRESH THYME #108"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_GLENELLYNFAMILYEYECARE(self):
        desc  = "GLEN ELLYN FAMILY EYECARE"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Vision Care")

    def test_GLENOAK(self):
        desc  = "GLEN OAK"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_GOOGLEYOUTUBETV1600AMPHITHEATREPKWY650253000094043CAUSA(self):
        desc  = "GOOGLE *YOUTUBE TV 1600 AMPHITHEATRE PKWY 650-253-0000 94043 CA USA"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_HAMPTONINNampSUITESFampB(self):
        desc  = "HAMPTON INN &amp; SUITES F&amp;B"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_HEATHERCUSHINGDIRECTDEPPPDID9444444404(self):
        desc  = "HEATHER CUSHING  DIRECT DEP                 PPD ID:  9444444404"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Paycheck")

    def test_HELPMAXCOM(self):
        desc  = "HELP.MAX.COM"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Entertainment")

    def test_HOMEGOODS316(self):
        desc  = "HOMEGOODS #316"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_ILSOSINTVEHRENEWAL(self):
        desc  = "ILSOS INT VEH RENEWAL"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_ILTOLLWAYAUTOREPLENISH(self):
        desc  = "IL TOLLWAY-AUTOREPLENISH"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_INSTAGIFTMADISONORI(self):
        desc  = "INSTAGIFT* MADISON ORI"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_JEWELOSCO3340(self):
        desc  = "JEWEL OSCO 3340"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_JEWELOSCOCOM3290(self):
        desc  = "JEWEL-OSCO.COM #3290"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Groceries")

    def test_JIMMYJOHNS359(self):
        desc  = "JIMMY JOHNS # 359"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_LEARNINGEXPRESSOFGLEN(self):
        desc  = "LEARNING EXPRESS OF GLEN"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_LENSACEHDWE(self):
        desc  = "LENS ACE HDWE"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_MAHJONGGLEA(self):
        desc  = "MAHJONGGLEA"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_McDonalds10742(self):
        desc  = "McDonalds 10742"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_McDonalds12638(self):
        desc  = "McDonalds 12638"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_McDonalds2966(self):
        desc  = "McDonalds 2966"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_McDonalds36138(self):
        desc  = "McDonalds 36138"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_McDonalds73(self):
        desc  = "McDonalds 73"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_MFSUSALOANPAYMBILLPAY13857746951WEBID7529240811(self):
        desc  = "MFSUSA LOAN PAYM BILL PAY   13857746951     WEB ID:  7529240811"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_MFSUSALOANPAYMBILLPAY13920841321WEBID7529240811(self):
        desc  = "MFSUSA LOAN PAYM BILL PAY   13920841321     WEB ID:  7529240811"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_MICROSOFTG0720718701MICROSOFTWAYREDMOND98052WAUSA(self):
        desc  = "MICROSOFT-G072071870 1 MICROSOFT WAY REDMOND 98052 WA USA"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_MICROSOFTG076573888ONEMICROSOFTWAYMSBILLINFO98052WAUSA(self):
        desc  = "MICROSOFT#G076573888 ONE MICROSOFT WAY MSBILL.INFO 98052 WA USA"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_MilkStreetMagazine(self):
        desc  = "Milk Street Magazine"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_MONTHLYINSTALLMENTS1OF12(self):
        desc  = "MONTHLY INSTALLMENTS (1 OF 12)"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_MONTHLYINSTALLMENTS5OF12(self):
        desc  = "MONTHLY INSTALLMENTS (5 OF 12)"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_MONTHLYINSTALLMENTS6OF12(self):
        desc  = "MONTHLY INSTALLMENTS (6 OF 12)"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_MORTONARBORETUM(self):
        desc  = "MORTON ARBORETUM"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_NATLFINSVCLLCEFTPPDID1035141375(self):
        desc  = "NATL FIN SVC LLC EFT                        PPD ID:  1035141375"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_NicorGasGASPAYMNTPPDID8121119770(self):
        desc  = "Nicor Gas        GAS PAYMNT                 PPD ID:  8121119770"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_NORTHWESTERNMUISAPYMENTPPDID9000596067(self):
        desc  = "NORTHWESTERN MU  ISA PYMENT                 PPD ID:  9000596067"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_OLIVENVINNIES(self):
        desc  = "OLIVE'N VINNIES"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_OnlineTransferfromCHK9812transaction23857390859(self):
        desc  = "Online Transfer from CHK ...9812 transaction#:  23857390859"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_PARKCHICAGOMOBILE(self):
        desc  = "PARK CHICAGO MOBILE"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_Peacock7C94APremium(self):
        desc  = "Peacock 7C94A Premium"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_PeacockC12B6Premium(self):
        desc  = "Peacock C12B6 Premium"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_PeacockX7564Premium(self):
        desc  = "Peacock X7564 Premium"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_PETESFRESHMARKET15(self):
        desc  = "PETE'S FRESH MARKET #15"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_REMOTEONLINEDEPOSIT1(self):
        desc  = "REMOTE ONLINE DEPOSIT #          1"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_SHUTTERFLYINC(self):
        desc  = "SHUTTERFLY  INC."
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_SLICEGINOSEAST(self):
        desc  = "SLICE*GINOSEAST"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_SOUTHWES5262303203788(self):
        desc  = "SOUTHWES    5262303203788"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_Spectrum(self):
        desc  = "Spectrum"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_SPEEDWAY06621VALPARAISO(self):
        desc  = "SPEEDWAY 06621 VALPARAISO"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_SPEEDWAY06684WANATAHIN(self):
        desc  = "SPEEDWAY 06684 WANATAH IN"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_SPMARCELSCULINARYEX(self):
        desc  = "SP MARCELS CULINARY EX"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_SPTHEGREATESCAPE(self):
        desc  = "SP THE GREAT ESCAPE"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_SQEMBASSYTHEATREFOUND(self):
        desc  = "SQ *EMBASSY THEATRE FOUND"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_SQNORTHWESTERNUNIVERSI(self):
        desc  = "SQ *NORTHWESTERN UNIVERSI"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_STATEFARMINSURANCE(self):
        desc  = "STATE FARM  INSURANCE"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_SWIM2000(self):
        desc  = "SWIM 2000"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TCKTWEBLANCONOAHHICKS685MARKETSTSTE200800965482794105CAUSA(self):
        desc  = "TCKTWEB*LANCONOAHHICKS685 MARKET ST STE 200 800-965-4827 94105 CA USA"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TheBookstoreofGlenEll(self):
        desc  = "The Bookstore of Glen Ell"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_THEHOMEDEPOT1916(self):
        desc  = "THE HOME DEPOT #1916"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TJMAXX0234(self):
        desc  = "TJMAXX #0234"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TRADERJOES680(self):
        desc  = "TRADER JOE S #680"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTAampGSUBSANDWICHS(self):
        desc  = "TST* A &amp; G SUB SANDWICH S"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTAGAVESIDEBAR(self):
        desc  = "TST*AGAVE SIDE BAR"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTALTIROLATINFUSION(self):
        desc  = "TST* ALTIRO LATIN FUSION-"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTELLASITALIANPUB(self):
        desc  = "TST*ELLAS ITALIAN PUB -"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTFISHCAMPONBROADCR(self):
        desc  = "TST*FISHCAMP ON BROAD CR"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTHOPSampPIE(self):
        desc  = "TST*HOPS &amp; PIE"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTKOZEWINE(self):
        desc  = "TST* KOZE WINE"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTLEYEBUBCITYJO(self):
        desc  = "TST* LEYE - BUB CITY - JO"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTMAINSTREETPUB(self):
        desc  = "TST* MAIN STREET PUB"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTNOBELHOUSEGLENE(self):
        desc  = "TST*NOBEL HOUSE - GLEN E"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTPUBLICANQUALITYMEA(self):
        desc  = "TST* PUBLICAN QUALITY MEA"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTROSEMARYANDJEANS(self):
        desc  = "TST* ROSEMARY AND JEAN'S"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTSTEADYEDDYS(self):
        desc  = "TST*STEADY EDDYS"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTSTOLPISLANDTHEATER(self):
        desc  = "TST*STOLP ISLAND THEATER"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTTENMILEHOUSE(self):
        desc  = "TST*TEN MILE HOUSE"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_TSTTHEPUBLICAN(self):
        desc  = "TST*THE PUBLICAN"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_UTDALLAS(self):
        desc  = "U.T. DALLAS"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_VCOStMarksEpiscop(self):
        desc  = "VCO*St. Mark's Episcop"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_VENMOPAYMENT1039344019419WEBID3264681992(self):
        desc  = "VENMO            PAYMENT    1039344019419   WEB ID:  3264681992"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_VENMOPAYMENT1039615838717WEBID3264681992(self):
        desc  = "VENMO            PAYMENT    1039615838717   WEB ID:  3264681992"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_VENMOPAYMENT1039844382989WEBID3264681992(self):
        desc  = "VENMO            PAYMENT    1039844382989   WEB ID:  3264681992"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_VERIZONWIRELESSPAYMENTSPPDID7223344794(self):
        desc  = "VERIZON WIRELESS PAYMENTS                   PPD ID:  7223344794"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_VILLAGEGARAGEANDTIRE(self):
        desc  = "VILLAGE GARAGE AND TIRE"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_VILLAGEOFGLENPPDPPDID1366005897(self):
        desc  = "VILLAGE OF GLEN  PPD                        PPD ID:  1366005897"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_WALGREENS6294(self):
        desc  = "WALGREENS #6294"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_WORLDMARKET75(self):
        desc  = "WORLD MARKET  #75"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_XEROSHOES(self):
        desc  = "XERO SHOES"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_ZellepaymentfromKEVINTOYEBACiheajwwsm(self):
        desc  = "Zelle payment from KEVIN TOYE BACiheajwwsm"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")

    def test_ZellepaymentfromWILLIAMLINDSTROMWFCT0YKW8QD7(self):
        desc  = "Zelle payment from WILLIAM LINDSTROM WFCT0YKW8QD7"
        result = suggest_subcategory(desc)
        self.assertEqual(result, "Fast Food")


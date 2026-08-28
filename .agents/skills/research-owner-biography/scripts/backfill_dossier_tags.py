from __future__ import annotations

import argparse
import filecmp
import json
import re
import shutil
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.io_utils import atomic_write_json
from src.tags import CanonicalTag, TagCatalogue, load_tag_catalogue, resolve_dossier_tags
from validate_dossier import validate


DEFAULT_DOSSIER_DIR = REPO_ROOT / "output" / "owner-research" / "all-by-loa"
DEFAULT_CATALOGUE = REPO_ROOT / "config" / "owner-tags.json"
LEGACY_SOURCE_SCHEMA = 7
TARGET_SCHEMA = 8
SUPPORTED_SOURCE_SCHEMAS = {LEGACY_SOURCE_SCHEMA, TARGET_SCHEMA}


# Counts from the earlier whole-corpus tag review. They are regression signals,
# not quotas: the migration keeps dossier evidence authoritative when it differs.
PRIOR_REVIEW_COUNTS = {
    "Commercial ship management": 46,
    "Private equity": 43,
    "Professional sports ownership": 37,
    "Tanker shipping": 35,
    "Environmental conservation": 31,
    "Aviation": 30,
    "Dry-bulk shipping": 30,
    "Luxury hospitality": 29,
    "Royalty": 29,
    "Football": 28,
    "Renewable energy / energy transition": 26,
    "Steel": 25,
    "Venture capital": 23,
    "Maritime tourism": 22,
    "Enterprise software": 22,
    "Shipbuilding": 21,
    "Cancer research / support": 20,
    "Biotechnology": 20,
    "Contemporary art": 19,
    "Art collector": 18,
    "Motorsport": 18,
    "Fintech": 17,
    "Marine / ocean conservation": 16,
    "Artificial intelligence": 15,
    "Filmmaking": 15,
    "Inventor": 15,
    "Sea captain / master mariner": 15,
    "Container shipping": 14,
    "Author": 13,
    "Hedge funds": 13,
    "Wine production": 13,
    "Cruise industry": 12,
    "Humanitarian aid": 12,
    "Marine engineering": 11,
    "Maritime technology": 11,
    "Data centres": 10,
    "E-commerce": 10,
    "House of Saud": 9,
    "Medical devices": 9,
    "Restaurant franchising": 9,
    "Competitive sailing": 8,
    "Ice hockey": 8,
    "Physician": 8,
    "Pilot": 8,
    "American football": 7,
    "Cloud computing": 7,
    "Digital payments": 7,
    "Equestrian sport": 7,
    "Golf": 7,
    "Permanent capital": 7,
    "Al Nahyan": 6,
    "Basketball": 6,
    "British peerage": 6,
    "Cryptocurrency": 6,
    "Naval architect": 6,
    "Recycling / waste management": 6,
    "Satellite technology": 6,
    "Television producer": 6,
    "Video games": 6,
    "Al Maktoum": 5,
    "Cybersecurity": 5,
    "Formula 1": 5,
    "Horse racing": 5,
    "LNG": 5,
    "Spaceflight": 5,
    "Aerospace": 4,
    "Al Thani": 4,
    "Tennis": 4,
    "Trial lawyer": 4,
    "Baseball": 3,
    "Classic-car collector": 3,
    "Guitarist": 3,
    "NASCAR": 3,
    "Rock music": 3,
    "Songwriter": 3,
    "Al Khalifa": 2,
    "DJ": 2,
    "Electronic dance music": 2,
    "Record label founder": 2,
    "Al Bu Said": 1,
    "Alaouite dynasty": 1,
    "Norwegian royal family": 1,
    "Boxing": 1,
    "Apple": 1,
}
PRIOR_REVIEW_COUNTS.update(
    {
        "3G Capital": 2,
        "ABC (American Broadcasting Company)": 2,
        "Aegean Oil": 2,
        "Aegean Shipping": 2,
        "Amway": 3,
        "ArcelorMittal": 2,
        "Arison family": 3,
        "Armani family": 3,
        "Artal Group": 2,
        "Aston Martin": 2,
        "Atzaró Group": 2,
        "Bakker–Overvast family": 2,
        "Cababie Daniel family": 2,
        "Carnival Corporation": 3,
        "Celebrity Cruises": 2,
        "Chandris family": 2,
        "Chandris Group": 2,
        "Chouest family": 2,
        "Citicorp Venture Capital": 3,
        "Constellation Brands": 2,
        "CVC Capital Partners": 4,
        "Della Valle family": 2,
        "Disney": 4,
        "Dragnis family": 2,
        "Duff Capital Investors": 2,
        "Duff family": 2,
        "easyJet": 2,
        "eBay": 2,
        "EchoPark": 2,
        "Edgewood Properties": 2,
        "Edison Chouest Offshore": 2,
        "Evraz": 4,
        "Ford": 5,
        "Fox Corporation": 2,
        "Getty family": 2,
        "GICSA": 2,
        "Giorgio Armani": 3,
        "Glencore": 3,
        "Goldman Sachs": 9,
        "Google": 4,
        "Gravanis family": 2,
        "Gucci family": 2,
        "Haji-Ioannou family": 2,
        "Hall family": 2,
        "Hidrostroy": 2,
        "Hogan": 2,
        "INEOS": 2,
        "Invus": 2,
        "Jim Moran Foundation": 2,
        "Koç family": 4,
        "Koç Holding": 4,
        "Latsco": 2,
        "Latsis family": 4,
        "Laurie family": 2,
        "Lowy family": 2,
        "M1 Group": 2,
        "Marlink": 2,
        "Martinos family": 3,
        "Mattei family": 2,
        "Mattei Holdings": 2,
        "Maveli": 2,
        "Melissanidis family": 2,
        "Metalloinvest": 2,
        "Microsoft": 6,
        "Mikati family": 2,
        "Moran family": 2,
        "Morris family": 2,
        "Murdoch family": 2,
        "News Corp": 2,
        "Nirjhara": 2,
        "Ofer family": 2,
        "OmniAccess": 2,
        "Orascom": 2,
        "Oscars Group": 2,
        "Overvast": 2,
        "Packer family": 2,
        "Papalekas family": 2,
        "Pears family": 3,
        "Perfetti family": 2,
        "Perfetti Van Melle": 2,
        "Pirelli": 2,
        "Pixmania": 2,
        "Powell family": 2,
        "Pure Cremation": 2,
        "Reuben Brothers": 2,
        "Reuben family": 2,
        "Roemmers family": 2,
        "Rosenblum family": 2,
        "Royal Caribbean": 3,
        "Sands family": 2,
        "Sawiris family": 2,
        "Schmidt family": 2,
        "Sibneft": 3,
        "Smith family (Sonic Automotive)": 2,
        "Sonic Automotive": 2,
        "Southern Tire Mart": 2,
        "Speedway Motorsports": 2,
        "Steam": 2,
        "Tchenguiz family": 2,
        "Tod's": 2,
        "Toyota": 6,
        "USM": 2,
        "Valve": 2,
        "Van Andel family": 2,
        "Walker family": 2,
        "Walker Marine Group": 2,
        "Walmart": 4,
        "Walton family": 4,
        "Wee family": 2,
        "Westfield": 2,
        "William Pears Group": 3,
        "Yıldırım family": 2,
        "Yoda Group": 2,
        "Zhelev family": 2,
    }
)


MATERIAL_ASSOCIATION_PATTERN = re.compile(
    r"\b(?:found(?:er|ed)?|cofounder|co founded|chief executive|ceo|chair(?:man|woman)?|"
    r"president|director|partner|principal|owner(?:ship)?|owned|stake|shareholder|"
    r"holdings?|inherited|fortune|wealth|career|worked|joined|led|built|created|"
    r"launched|established|acquired|sold|buyout|investment|invested|employee|"
    r"engineer|executive|developer|producer|publisher|architect|designer|family|"
    r"dealership|distributor|distribution|purchases?|purchased|funded|financed|"
    r"donated|placed)\b"
)
FAMILY_CONTEXT_PATTERN = re.compile(
    r"\b(?:family|dynasty|inherit(?:ed|ance)?|heir|succession|brother|sister|father|"
    r"mother|son|daughter|spouse|wife|husband|widow|cousin|uncle|aunt|nephew|"
    r"niece|grandfather|grandmother|fortune|family controlled|family owned)\b"
)
ROYAL_CONTEXT_PATTERN = re.compile(
    r"\b(?:royal|royalty|ruling family|dynasty|monarch|monarchy|king|queen|prince|"
    r"princess|crown|throne|sovereign|emir|sultan|sheikh)\b"
)
GOVERNMENT_OWNER_NAME_PATTERN = re.compile(
    r"\b(?:government|ministry|municipality|municipal council|city council|"
    r"state authority|public authority)\b|(?:^|\s)city$"
)
GOVERNMENT_OWNERSHIP_PATTERNS = (
    r"\b(?:government|state|federal|national|municipal|local government|public) "
    r"(?:administration|authority|body|department|entity|institution|ministry|"
    r"agency|enterprise)\b",
    r"\b(?:government of|government itself|state administration|municipality|"
    r"city council)\b",
    r"\b(?:is|was|remains|became) (?:an? |the )?(?:wholly |majority )?"
    r"(?:government|state) owned(?: \w+){0,3} "
    r"(?:company|enterprise|entity|institution|body|organisation|organization)\b",
    r"\b(?:is|was|remains) (?:wholly |majority )?owned by (?:the )?"
    r"(?:government|state|federal government|national government|municipality)\b",
    r"\b(?:government|state) ownership\b",
)
PHILANTHROPY_CONTEXT_PATTERN = re.compile(
    r"\b(?:philanthrop(?:y|ic|ist)|charit(?:y|able)|foundation|nonprofit|non profit|"
    r"donat(?:e|ed|ion|ions)|grant(?:s|making)?|endow(?:ed|ment)|civic work|"
    r"social impact|public benefit|gift(?:s|ed)?)\b"
)
NON_PHILANTHROPIC_FOUNDATION_PATTERN = re.compile(
    r"\b(?:academic|commercial|financial|operating|technical|wealth) foundation\b|"
    r"\bfoundation (?:of|for) (?:his|her|the|a|an) "
    r"(?:career|fortune|wealth|business|company|platform|success)\b"
)
PRIVATE_EQUITY_ROLE_PATTERN = re.compile(
    r"\b(?:private equity|buyout) (?:investor|investment|firm|fund|funds|partner|"
    r"principal|founder|executive|manager|career|platform|business|portfolio)\b|"
    r"\b(?:founded|co founded|built|led|managed|joined|chairs?|partner at|principal at) "
    r"(?:an? )?(?:private equity|buyout)\b"
)
PRIVATE_EQUITY_COUNTERPARTY_PATTERN = re.compile(
    r"\b(?:sold to|acquired by|bought by|backed by|controlled by|owned by|"
    r"investment from) (?:an? )?(?:\w+ )?(?:private equity|buyout)\b"
)
AVIATION_ROLE_PATTERN = re.compile(
    r"\b(?:aviation|airline|aircraft|airport|flight|flying) "
    r"(?:business|company|companies|industry|operator|operations|services|school|"
    r"academy|manufacturer|manufacturing|leasing|career|entrepreneur|executive|"
    r"founder|owner|chairman|chief executive|training)\b|"
    r"\b(?:airline|aviation) (?:founder|owner|chairman|chief executive|entrepreneur)\b|"
    r"\b(?:licensed|certified|commercial|military|private|airline|test) "
    r"(?:pilot|aviator)\b|\b(?:pilot|aviator) and\b|\bis both [^.]{0,50}\bpilot\b"
)


TOPIC_PATTERNS: dict[str, tuple[str, ...]] = {
    "Aerospace": (
        r"\baerospace\b",
        r"\baircraft (?:manufactur|engineering|systems?)",
        r"\bspace and aviation\b",
    ),
    "Artificial intelligence": (
        r"\bartificial intelligence\b",
        r"\bmachine learning\b",
        r"\bai (?:company|companies|platform|software|systems?|research|models?)\b",
    ),
    "Aviation": (
        r"\baviation\b",
        r"\bairline(?:s)?\b",
        r"\baircraft (?:business|leasing|manufactur|operator|operations?|services?)\b",
        r"\bprivate jet(?:s)?\b",
    ),
    "Biotechnology": (
        r"\bbiotech(?:nology)?\b",
        r"\bbiopharma(?:ceutical)?\b",
        r"\bgenomics?\b",
        r"\bgene (?:therapy|editing|sequencing)\b",
    ),
    "Cloud computing": (
        r"\bcloud computing\b",
        r"\bcloud (?:infrastructure|platform|services?|software)\b",
    ),
    "Commercial ship management": (
        r"\bship management\b",
        r"\bshipping management\b",
        r"\bvessel management\b",
        r"\bfleet management\b",
        r"\btechnical and commercial management\b",
        r"\btechnical management of (?:ships|vessels|fleets)\b",
        r"\bshipowning and management\b",
        r"\bmanaged (?:a |the )?(?:merchant |commercial )?fleet\b",
        r"\bthird party ship",
    ),
    "Container shipping": (
        r"\bcontainer shipping\b",
        r"\bcontainer line\b",
        r"\bcontainer carriers?\b",
        r"\bcontainerships?\b",
        r"\bcontainer vessels?\b",
    ),
    "Cruise industry": (
        r"\bcruise (?:industry|line|lines|company|companies|operator|business|group)\b",
        r"\bpassenger cruising\b",
    ),
    "Cryptocurrency": (
        r"\bcryptocurrenc(?:y|ies)\b",
        r"\bcrypto (?:exchange|platform|company|assets?|trading|business)\b",
        r"\bbitcoin\b",
        r"\bblockchain\b",
    ),
    "Cybersecurity": (
        r"\bcyber ?security\b",
        r"\bcomputer security\b",
        r"\binformation security\b",
    ),
    "Data centres": (
        r"\bdata cent(?:re|er)s?\b",
        r"\bcolocation\b",
    ),
    "Digital payments": (
        r"\bdigital payments?\b",
        r"\bpayments? platform\b",
        r"\bpayment processing\b",
        r"\bmobile payments?\b",
        r"\belectronic payments?\b",
    ),
    "Dry-bulk shipping": (
        r"\bdry bulk\b",
        r"\bbulk shipping\b",
        r"\bbulk carriers?\b",
        r"\bdry cargo fleet\b",
        r"\bbulkers?\b",
    ),
    "E-commerce": (
        r"\be commerce\b",
        r"\bonline (?:retail|marketplace|commerce|shopping)\b",
        r"\binternet retail\b",
    ),
    "Enterprise software": (
        r"\benterprise software\b",
        r"\benterprise (?:applications?|technology|systems?|data platform|information services?)\b",
        r"\bbusiness software\b",
        r"\bcorporate software\b",
        r"\bsoftware (?:company|platform|systems?) (?:for|serving) (?:business|enterprise)",
        r"\bsoftware for (?:businesses|companies|corporate clients|enterprises)\b",
        r"\bdatabase software\b",
    ),
    "Fintech": (
        r"\bfintech\b",
        r"\bfinancial technology\b",
        r"\bdigital bank(?:ing)?\b",
        r"\bonline brokerage\b",
    ),
    "Gambling": (
        r"\bgambling\b",
        r"\bcasinos?\b",
        r"\bcasino gaming\b",
        r"\bgaming (?:operator|operations?|resort|venues?)\b",
        r"\b(?:online|mobile|internet|sports) betting\b",
        r"\bbookmak(?:er|ing)\b",
    ),
    "Hedge funds": (
        r"\bhedge fund(?:s)?\b",
        r"\bhedge fund manager\b",
    ),
    "LNG": (
        r"\blng\b",
        r"\bliquefied natural gas\b",
        r"\blng carriers?\b",
    ),
    "Luxury hospitality": (
        r"\bluxury hospitality\b",
        r"\bluxury hotels?\b",
        r"\bluxury resorts?\b",
        r"\bfive star (?:hotel|resort)\b",
        r"\bhotel (?:portfolio|group|ownership|operator|business)\b",
        r"\bhotels and resorts\b",
    ),
    "Marine engineering": (
        r"\bmarine engineering\b",
        r"\bmarine engineer\b",
        r"\bnaval engineering\b",
        r"\boffshore engineering\b",
    ),
    "Maritime technology": (
        r"\bmaritime technology\b",
        r"\bmarine technology\b",
        r"\bshipping technology\b",
        r"\bmaritime (?:software|communications?|systems?|platform)\b",
        r"\bmarine electronics\b",
    ),
    "Maritime tourism": (
        r"\bmaritime tourism\b",
        r"\byacht charter\b",
        r"\bmarine tourism\b",
        r"\bmarina (?:business|development|operator|operations?)\b",
        r"\bferr(?:y|ies) (?:business|operator|services?)\b",
    ),
    "Medical devices": (
        r"\bmedical devices?\b",
        r"\bmedical equipment\b",
        r"\bhealthcare devices?\b",
        r"\bprosthetics?\b",
    ),
    "Permanent capital": (
        r"\bpermanent capital\b",
        r"\bevergreen capital\b",
        r"\bpermanent capital vehicle\b",
    ),
    "Private equity": (
        r"\bprivate equity\b",
        r"\bbuyout (?:firm|fund|funds|investor|investing)\b",
        r"\bleveraged buyouts?\b",
    ),
    "Recycling / waste management": (
        r"\brecycling\b",
        r"\bwaste management\b",
        r"\bwaste processing\b",
        r"\bscrap metal\b",
    ),
    "Renewable energy / energy transition": (
        r"\brenewable energy\b",
        r"\benergy transition\b",
        r"\bsolar (?:energy|power|projects?|farms?)\b",
        r"\bwind (?:energy|power|projects?|farms?)\b",
        r"\bgreen hydrogen\b",
        r"\bclean energy\b",
    ),
    "Restaurant franchising": (
        r"\brestaurant franchis(?:e|es|ing)\b",
        r"\bfranchised restaurants?\b",
        r"\bfood franchis(?:e|es|ing)\b",
        r"\bfast food franchis",
    ),
    "Satellite technology": (
        r"\bsatellite technology\b",
        r"\bsatellite (?:company|companies|communications?|systems?|operator|network)\b",
        r"\bcommercial satellites?\b",
    ),
    "Shipbuilding": (
        r"\bshipbuilding\b",
        r"\bshipbuilder\b",
        r"\bshipyards?\b",
        r"\bbuilds? (?:commercial |naval )?ships\b",
    ),
    "Spaceflight": (
        r"\bspaceflight\b",
        r"\bspace flight\b",
        r"\bspace exploration\b",
        r"\bspace launch\b",
        r"\borbital (?:flight|mission|launch)\b",
        r"\bcommercial space\b",
    ),
    "Steel": (
        r"\bsteel (?:business|company|companies|industry|maker|making|producer|production|group|mills?)\b",
        r"\bsteelmaking\b",
        r"\bsteel magnate\b",
    ),
    "Tanker shipping": (
        r"\btanker shipping\b",
        r"\btanker fleet\b",
        r"\btankers?\b",
        r"\boil tankers?\b",
        r"\bproduct tankers?\b",
        r"\bchemical tankers?\b",
        r"\btanker owner\b",
    ),
    "Venture capital": (
        r"\bventure capital\b",
        r"\bventure fund(?:s)?\b",
        r"\bventure investor\b",
        r"\bstartup investor\b",
    ),
    "Video games": (
        r"\bvideo games?\b",
        r"\bgame (?:developer|development|studio|publisher|distribution)\b",
        r"\b(?:computer|console|mobile|online) games?\b",
    ),
    "Wine production": (
        r"\bwine production\b",
        r"\bwinemaker\b",
        r"\bwinemaking\b",
        r"\bwinery\b",
        r"\bvineyard(?:s)?\b",
    ),
    "Art collector": (
        r"\bart collector\b",
        r"\bart collection\b",
        r"\bart collecting\b",
        r"\bcollector of (?:modern |contemporary |postwar )?art\b",
        r"\bcollecting (?:modern |contemporary |postwar )?art\b",
        r"\bcollects? (?:modern |contemporary )?art\b",
    ),
    "Contemporary art": (
        r"\bcontemporary art\b",
        r"\bmodern and contemporary art\b",
        r"\bcontemporary artists?\b",
    ),
    "Classic-car collector": (
        r"\bclassic car collector\b",
        r"\bclassic car collection\b",
        r"\bclassic car collecting\b",
        r"\bvintage car collector\b",
        r"\bvintage car collection\b",
    ),
    "Filmmaking": (
        r"\bfilmmak(?:er|ing)\b",
        r"\bfilm (?:director|producer|production|studio|career)\b",
        r"\bmotion picture (?:director|producer|production)\b",
    ),
    "Electronic dance music": (
        r"\belectronic dance music\b",
        r"\bedm\b",
    ),
    "Rock music": (
        r"\brock musician\b",
        r"\brock music\b",
        r"\brock and roll\b",
        r"\brock band\b",
        r"\brock guitarist\b",
    ),
    "Author": (
        r"\bauthor\b",
        r"\bnovelist\b",
        r"\bwrote (?:several |multiple |[a-z]+ )?(?:books?|novels?|memoirs?)\b",
        r"\bseries of books\b",
    ),
    "DJ": (
        r"\bdisc jockey\b",
        r"\bdj\b",
    ),
    "Guitarist": (
        r"\bguitarist\b",
        r"\blead guitar\b",
    ),
    "Inventor": (
        r"\binventor\b",
        r"\binvented\b",
        r"\bpatents? (?:for|covering|on)\b",
        r"\bnamed on (?:several |multiple |\w+ )?patents?\b",
    ),
    "Naval architect": (
        r"\bnaval architect\b",
        r"\bnaval architecture\b",
    ),
    "Physician": (
        r"\bphysician\b",
        r"\bmedical doctor\b",
        r"\b(?:trained|practised|practiced|worked) as (?:an? )?(?:doctor|surgeon)\b",
        r"\b(?:cardiologist|oncologist|radiologist|orthopaedic surgeon|neurosurgeon)\b",
    ),
    "Pilot": (
        r"\b(?:certified|licensed|commercial|military|private|airline|test) pilot\b",
        r"\bcertified (?:jet and helicopter|private|commercial) pilot\b",
        r"\bmilitary aviator\b",
        r"\b(?:is|was|became|trained as|worked as) (?:an? )?(?:airline |commercial |military |test )?pilot\b",
        r"\bis both [^.]{0,50}\bpilot\b",
        r"\b(?:saudi|emirati|american|british|turkish) aviator\b",
        r"\bpilot licence\b",
        r"\blicensed pilot\b",
    ),
    "Record label founder": (
        r"\bfounded (?:the )?(?:record |music )?label\b",
        r"\brecord label founder\b",
        r"\bco founded (?:the )?(?:record |music )?label\b",
    ),
    "Sea captain / master mariner": (
        r"\bmaster mariner\b",
        r"\bsea captain\b",
        r"\bmerchant navy captain\b",
        r"\bship captain\b",
        r"\bqualified as (?:a )?captain\b",
        r"\bworking captain\b",
        r"\bprofessional captain\b",
        r"\bcharter captain\b",
        r"\bmaritime entrepreneur(?: and|,) captain\b",
        r"\b(?:croatian|french|greek|turkish) captain\b",
        r"\bprogressed to captain\b",
        r"\bcaptain s and engineering licences\b",
        r"\bseventh generation captain\b",
        r"^captain [a-z]",
        r"\ba captain from a shipowning family\b",
    ),
    "Songwriter": (
        r"\bsongwriter\b",
        r"\bwrote (?:songs|music)\b",
    ),
    "Television producer": (
        r"\btelevision producer\b",
        r"\btv producer\b",
        r"\bproduced television\b",
    ),
    "Trial lawyer": (
        r"\btrial lawyer\b",
        r"\btrial attorney\b",
        r"\bplaintiff(?:s)? lawyer\b",
        r"\bpersonal injury lawyer\b",
    ),
    "American football": (
        r"\bamerican football\b",
        r"\bnfl\b",
        r"\bnational football league\b",
        r"\bsuper bowl\b",
    ),
    "Baseball": (
        r"\bbaseball\b",
        r"\bmajor league baseball\b",
        r"\bmlb\b",
    ),
    "Basketball": (
        r"\bbasketball\b",
        r"\bnational basketball association\b",
        r"\bnba\b",
    ),
    "Boxing": (
        r"\bprofessional boxer\b",
        r"\bboxing (?:career|champion|championship|promoter|promotion|hall of fame)\b",
        r"\bboxer (?:and|who|whose|with|from)\b",
        r"\bworld champion from (?:flyweight|welterweight)",
    ),
    "Competitive sailing": (
        r"\bcompetitive sailing\b",
        r"\bsailing competition\b",
        r"\bsailing career\b",
        r"\bolympic sail(?:ing|or)\b",
        r"\byacht racing\b",
        r"\bregatta(?:s)?\b",
    ),
    "Equestrian sport": (
        r"\bequestrian\b",
        r"\bshow jumping\b",
        r"\bdressage\b",
        r"\bpolo (?:player|team|club|career)\b",
    ),
    "Football": (
        r"\bfootball (?:club|team|career|league|ownership|owner|holdings|investment|"
        r"administration|governance|federation|business)\b",
        r"\bsoccer (?:club|team|career|league|ownership|owner|holdings|investment)\b",
        r"\b(?:english|european|professional|club) football\b",
        r"\b(?:uefa|fifa|premier league|serie a|la liga)\b",
    ),
    "Formula 1": (
        r"\bformula 1\b",
        r"\bformula one\b",
        r"\bf1 (?:team|constructor|racing|championship)\b",
    ),
    "Golf": (
        r"\bprofessional golfer\b",
        r"\bgolf (?:career|champion|championship|course|club|business)\b",
        r"\bpga tour\b",
    ),
    "Horse racing": (
        r"\bhorse racing\b",
        r"\bracehorse(?:s)?\b",
        r"\bthoroughbred (?:racing|breeding|stud)\b",
    ),
    "Ice hockey": (
        r"\bice hockey\b",
        r"\bnational hockey league\b",
        r"\bnhl\b",
        r"\bhockey (?:club|team|franchise|owner|ownership)\b",
    ),
    "Motorsport": (
        r"\bmotorsport\b",
        r"\bmotor racing\b",
        r"\bauto racing\b",
        r"\bracing team\b",
        r"\bracing driver\b",
    ),
    "NASCAR": (
        r"\bnascar\b",
        r"\bstock car racing\b",
    ),
    "Tennis": (
        r"\bprofessional tennis\b",
        r"\btennis (?:career|player|champion|championship|tournament)\b",
    ),
    "British peerage": (
        r"\bbritish peerage\b",
        r"\bbritish peer\b",
        r"\blife peer\b",
        r"\bhereditary peer\b",
        r"\bmember of the house of lords\b",
        r"\b(?:baron|viscount|earl) in the peerage\b",
        r"\b\d+(?:st|nd|rd|th) baron\b",
        r"\bcreation as baron\b",
    ),
}


PHILANTHROPY_DOMAINS: dict[str, tuple[str, ...]] = {
    "Cancer research / support": (
        r"\bcancer\b", r"\boncology\b", r"\btumou?r\b",
    ),
    "Humanitarian aid": (
        r"\bhumanitarian\b", r"\bdisaster relief\b", r"\bemergency relief\b",
        r"\brefugees?\b", r"\bfood aid\b", r"\bhousing (?:aid|relief|programme)\b",
    ),
}


CONSERVATION_PATTERNS: dict[str, tuple[str, ...]] = {
    "Environmental conservation": (
        r"\benvironmental conservation\b", r"\bnature conservation\b",
        r"\bconservation\b", r"\bwildlife protection\b",
        r"\benvironmental (?:work|philanthropy|initiatives?|programmes?|protection)\b",
        r"\bclimate (?:philanthropy|initiatives?|programmes?|work)\b",
        r"\bconservation initiatives?\b", r"\bprotect(?:ing|ion of) (?:nature|wildlife|habitats?)\b",
        r"\bwwf\b", r"\bbiodiversity\b",
    ),
    "Marine / ocean conservation": (
        r"\bmarine conservation\b", r"\bocean conservation\b",
        r"\bmarine protection\b", r"\bocean protection\b",
        r"\bprotect(?:ing|ion of) (?:the )?(?:ocean|sea|marine ecosystems?)\b",
        r"\bmarine biodiversity\b", r"\bocean health\b",
        r"\b(?:marine|ocean) (?:research|science|philanthropy|initiatives?|programmes?)\b",
    ),
}


IMPLIED_TAGS: dict[str, tuple[str, ...]] = {
    "Formula 1": ("Motorsport",),
    "NASCAR": ("Motorsport",),
    "Marine / ocean conservation": ("Environmental conservation",),
}


AMBIGUOUS_COMPANY_LABELS: dict[str, tuple[str, ...]] = {
    "3G Capital": ("3G Capital",),
    "Apple": ("Apple", "Apple Inc.", "Apple Computer"),
    "Celebrity Cruises": ("Celebrity Cruises",),
    "CVC Capital Partners": ("CVC Capital Partners", "Citicorp Venture Capital"),
    "Edison Chouest Offshore": ("Edison Chouest Offshore", "Chouest Group"),
    "M1 Group": ("M1 Group",),
    "Steam": ("Steam", "Steam platform"),
    "Valve": ("Valve", "Valve Corporation"),
}


EXPLICIT_FAMILY_PHRASE_TAGS = {
    "Hall family",
    "Morris family",
    "Powell family",
    "Sands family",
    "Smith family (Sonic Automotive)",
    "Walker family",
}
CURATED_FAMILY_OWNER_IDS: dict[str, frozenset[int]] = {
    "Armani family": frozenset({10424, 10425, 10426}),
    "Bakker–Overvast family": frozenset({200, 202}),
    "Cababie Daniel family": frozenset({7307, 7308}),
    "Hall family": frozenset({979, 980}),
    "Morris family": frozenset({7626, 7627}),
    "Powell family": frozenset({9850, 9851}),
    "Reuben family": frozenset({1811, 1812}),
    "Smith family (Sonic Automotive)": frozenset({2014, 2015}),
    "Walker family": frozenset({6949, 6950}),
    "Walton family": frozenset({1222, 2292, 2293, 3190}),
    "Wee family": frozenset({2464, 2465}),
    "Yıldırım family": frozenset({7206, 7702}),
}


@dataclass(frozen=True)
class Evidence:
    path: str
    text: str
    normalized: str
    source_ids: tuple[str, ...]
    direct_source_id: str | None = None


@dataclass(frozen=True)
class Match:
    tag: CanonicalTag
    evidence: tuple[Evidence, ...]
    method: str


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value).casefold()
    without_marks = "".join(
        character for character in decomposed
        if not unicodedata.combining(character)
    )
    expanded = without_marks.replace("&", " and ").replace("_", " ")
    return re.sub(r"[^\w]+", " ", expanded, flags=re.UNICODE).strip()


def _sentences(value: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"(?<=[.!?])\s+|\r?\n+", value)
        if item.strip()
    ]


def _source_ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _add_evidence(
    output: list[Evidence],
    *,
    path: str,
    text: Any,
    source_ids: Iterable[str],
    direct_source_id: str | None = None,
) -> None:
    if not isinstance(text, str):
        return
    for index, sentence in enumerate(_sentences(text)):
        normalized = _normalize(sentence)
        if normalized:
            output.append(
                Evidence(
                    path=f"{path}[{index}]",
                    text=sentence,
                    normalized=normalized,
                    source_ids=tuple(source_ids),
                    direct_source_id=direct_source_id,
                )
            )


def build_evidence(dossier: dict[str, Any]) -> tuple[list[Evidence], list[Evidence]]:
    claims: list[Evidence] = []
    source_evidence: list[Evidence] = []

    for field in ("biography", "long_biography"):
        value = dossier.get(field)
        if isinstance(value, dict):
            _add_evidence(
                claims,
                path=f"{field}.plain_text",
                text=value.get("plain_text"),
                source_ids=_source_ids(value.get("source_ids")),
            )

    brief = dossier.get("biography_brief")
    if isinstance(brief, dict):
        brief_sources = _source_ids(brief.get("source_ids"))
        for field in (
            "durable_identity",
            "defining_work",
            "formative_context",
            "decisive_moment",
            "character_detail",
        ):
            _add_evidence(
                claims,
                path=f"biography_brief.{field}",
                text=brief.get(field),
                source_ids=brief_sources,
            )
        for index, item in enumerate(brief.get("enduring_dimensions", [])):
            _add_evidence(
                claims,
                path=f"biography_brief.enduring_dimensions[{index}]",
                text=item,
                source_ids=brief_sources,
            )

    for field in (
        "wealth_creation_industry",
        "primary_industry",
        "wealth_origin",
        "wealth_relationship",
    ):
        value = dossier.get(field)
        if isinstance(value, dict):
            _add_evidence(
                claims,
                path=f"{field}.summary",
                text=value.get("summary"),
                source_ids=_source_ids(value.get("source_ids")),
            )

    note = dossier.get("editorial_note")
    if isinstance(note, dict):
        _add_evidence(
            claims,
            path="editorial_note.plain_text",
            text=note.get("plain_text"),
            source_ids=_source_ids(note.get("source_ids")),
        )

    for index, source in enumerate(dossier.get("sources", [])):
        if not isinstance(source, dict):
            continue
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id:
            continue
        for field in ("title", "publisher"):
            _add_evidence(
                source_evidence,
                path=f"sources[{index}].{field}",
                text=source.get(field),
                source_ids=(source_id,),
                direct_source_id=source_id,
            )
        for support_index, support in enumerate(source.get("supports", [])):
            _add_evidence(
                source_evidence,
                path=f"sources[{index}].supports[{support_index}]",
                text=support,
                source_ids=(source_id,),
                direct_source_id=source_id,
            )

    return claims, source_evidence


def _compile(patterns: Iterable[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern) for pattern in patterns)


def _matching(
    evidence: Iterable[Evidence],
    patterns: Iterable[str],
) -> list[Evidence]:
    compiled = _compile(patterns)
    return [
        item for item in evidence
        if any(pattern.search(item.normalized) for pattern in compiled)
    ]


def _label_pattern(label: str) -> str:
    normalized = _normalize(label)
    return rf"(?<!\w){re.escape(normalized)}(?!\w)"


def _company_patterns(tag: CanonicalTag) -> tuple[str, ...]:
    labels = AMBIGUOUS_COMPANY_LABELS.get(tag.name)
    if labels is None:
        labels = (tag.name, *tag.aliases)
    return tuple(_label_pattern(label) for label in labels)


def _material_company_matches(
    tag: CanonicalTag,
    claims: list[Evidence],
) -> list[Evidence]:
    patterns = _compile(_company_patterns(tag))
    output: list[Evidence] = []
    for item in claims:
        if not any(pattern.search(item.normalized) for pattern in patterns):
            continue
        if not MATERIAL_ASSOCIATION_PATTERN.search(item.normalized):
            continue
        if tag.name == "Steam" and not re.search(
            r"\b(?:valve|video games?|gaming|game distribution|software platform|"
            r"half life|team fortress)\b",
            item.normalized,
        ):
            continue
        if tag.name == "Valve" and not re.search(
            r"\b(?:video games?|gaming|game development|software engineer|steam|"
            r"half life|team fortress|joined valve|co founded valve)\b",
            item.normalized,
        ):
            continue
        if tag.name == "Ford" and not re.search(
            r"\b(?:ford motor|automotive|automobile|cars?|vehicles?|dealerships?|"
            r"dealers?|motor company|auto group)\b",
            item.normalized,
        ):
            continue
        output.append(item)
    return output


def _family_matches(
    tag: CanonicalTag,
    dossier: dict[str, Any],
    claims: list[Evidence],
) -> list[Evidence]:
    curated_ids = CURATED_FAMILY_OWNER_IDS.get(tag.name)
    if curated_ids is not None:
        person_id = dossier.get("owner", {}).get("person_id")
        if person_id not in curated_ids:
            return []
        family_claims = [
            item for item in claims
            if FAMILY_CONTEXT_PATTERN.search(item.normalized)
        ]
        if family_claims:
            return family_claims
        return [
            item for item in claims
            if item.path.startswith((
                "biography.plain_text",
                "biography_brief.durable_identity",
                "biography_brief.defining_work",
            ))
        ]

    canonical_phrase = _label_pattern(tag.name)
    explicit = [
        item for item in claims
        if re.search(canonical_phrase, item.normalized)
        and FAMILY_CONTEXT_PATTERN.search(item.normalized)
    ]
    if explicit:
        return explicit
    if tag.name in EXPLICIT_FAMILY_PHRASE_TAGS:
        return []

    owner_name = _normalize(
        str(dossier.get("owner", {}).get("display_name", ""))
    )
    canonical_base = re.sub(
        r"\s+family(?:\s+.*)?$",
        "",
        _normalize(tag.name),
    )
    aliases = [canonical_base]
    aliases.extend(
        re.sub(r"\s+family(?:\s+.*)?$", "", _normalize(alias))
        for alias in tag.aliases
    )
    aliases = [alias for alias in aliases if alias]
    subject_match = any(
        re.search(rf"(?:^|\s){re.escape(alias)}$", owner_name)
        for alias in aliases
    )
    if not subject_match:
        return []
    return [
        item for item in claims
        if FAMILY_CONTEXT_PATTERN.search(item.normalized)
    ]


def _royal_family_matches(
    tag: CanonicalTag,
    dossier: dict[str, Any],
    claims: list[Evidence],
) -> list[Evidence]:
    patterns = tuple(_label_pattern(label) for label in (tag.name, *tag.aliases))
    body_matches = _matching(claims, patterns)
    explicit = [
        item for item in body_matches
        if ROYAL_CONTEXT_PATTERN.search(item.normalized)
    ]
    if explicit:
        return explicit
    if tag.name == "House of Saud":
        saudi_royal = [
            item for item in claims
            if re.search(
                r"\b(?:saudi (?:prince|royal)|royal family member)\b",
                item.normalized,
            )
        ]
        if saudi_royal:
            return saudi_royal
    if tag.name == "Norwegian royal family":
        norwegian_monarch = [
            item for item in claims
            if re.search(
                r"\b(?:king harald|norway s (?:constitutional )?monarch|"
                r"norwegian (?:constitutional )?monarch)\b",
                item.normalized,
            )
        ]
        if norwegian_monarch:
            return norwegian_monarch
    owner_name = _normalize(
        str(dossier.get("owner", {}).get("display_name", ""))
    )
    if any(re.search(pattern, owner_name) for pattern in patterns):
        return [
            item for item in claims
            if ROYAL_CONTEXT_PATTERN.search(item.normalized)
        ]
    return []


def _philanthropy_matches(
    name: str,
    claims: list[Evidence],
) -> list[Evidence]:
    domain_patterns = _compile(PHILANTHROPY_DOMAINS[name])
    return [
        item for item in claims
        if PHILANTHROPY_CONTEXT_PATTERN.search(item.normalized)
        and not NON_PHILANTHROPIC_FOUNDATION_PATTERN.search(item.normalized)
        and any(pattern.search(item.normalized) for pattern in domain_patterns)
    ]


def _gambling_matches(
    dossier: dict[str, Any],
    claims: list[Evidence],
) -> list[Evidence]:
    direct = _matching(claims, TOPIC_PATTERNS["Gambling"])
    if direct:
        return direct
    classified_prefixes: set[str] = set()
    for field in ("wealth_creation_industry", "primary_industry"):
        value = dossier.get(field)
        if isinstance(value, dict) and value.get("classification") == (
            "gambling_casinos"
        ):
            classified_prefixes.add(f"{field}.summary")
    if not classified_prefixes:
        return []
    return [
        item
        for item in claims
        if item.path.startswith(tuple(classified_prefixes))
    ]


def _private_equity_matches(claims: list[Evidence]) -> list[Evidence]:
    topic_patterns = _compile(TOPIC_PATTERNS["Private equity"])
    output: list[Evidence] = []
    for item in claims:
        if not any(pattern.search(item.normalized) for pattern in topic_patterns):
            continue
        if PRIVATE_EQUITY_COUNTERPARTY_PATTERN.search(item.normalized):
            continue
        if item.path.startswith(("wealth_creation_industry.", "primary_industry.")):
            output.append(item)
            continue
        if PRIVATE_EQUITY_ROLE_PATTERN.search(item.normalized):
            output.append(item)
    return output


def _aviation_matches(
    dossier: dict[str, Any],
    claims: list[Evidence],
) -> list[Evidence]:
    classified = any(
        isinstance(dossier.get(field), dict)
        and dossier[field].get("classification") == "aviation_aerospace"
        for field in ("wealth_creation_industry", "primary_industry")
    )
    topic_patterns = _compile(TOPIC_PATTERNS["Aviation"])
    matches = [
        item for item in claims
        if any(pattern.search(item.normalized) for pattern in topic_patterns)
    ]
    if classified:
        return matches
    return [
        item for item in matches
        if item.path.startswith((
            "biography_brief.durable_identity",
            "biography_brief.defining_work",
            "biography_brief.enduring_dimensions",
        ))
        or AVIATION_ROLE_PATTERN.search(item.normalized)
    ]


def _football_matches(claims: list[Evidence]) -> list[Evidence]:
    patterns = _compile(TOPIC_PATTERNS["Football"])
    american = re.compile(
        r"\b(?:american football|national football league|nfl|super bowl)\b"
    )
    association = re.compile(
        r"\b(?:invest|holding|owner|ownership|club|federation|governance|chair|"
        r"professional|administration|career|president)\w*\b"
    )
    soccer_specific = re.compile(
        r"\b(?:football club|english football|european football|premier league|"
        r"serie a|la liga|uefa|fifa|soccer)\b"
    )
    dossier_has_american_football = any(
        american.search(item.normalized) for item in claims
    )
    dossier_has_soccer = any(
        soccer_specific.search(item.normalized) for item in claims
    )
    if dossier_has_american_football and not dossier_has_soccer:
        return []
    return [
        item for item in claims
        if (
            any(pattern.search(item.normalized) for pattern in patterns)
            or (
                re.search(r"\bfootball\b", item.normalized)
                and association.search(item.normalized)
            )
        )
        and not (
            american.search(item.normalized)
            and not soccer_specific.search(item.normalized)
        )
        and not re.search(
            r"\b(?:car football|vehicle[^.]{0,35}football|football game|"
            r"game developer|game studio|rocket league)\b",
            item.normalized,
        )
    ]


def _british_peerage_matches(
    dossier: dict[str, Any],
    claims: list[Evidence],
    source_evidence: list[Evidence],
) -> list[Evidence]:
    body = _matching(claims, TOPIC_PATTERNS["British peerage"])
    if body:
        return body
    owner_name = _normalize(
        str(dossier.get("owner", {}).get("display_name", ""))
    )
    if not re.search(r"\b(?:lord|baron|viscount|earl)\b", owner_name):
        return []
    direct = _matching(
        source_evidence,
        (
            r"\b(?:life|hereditary) peerage\b",
            r"\bcreation (?:as|of) baron\b",
            r"\bhouse of lords\b",
            r"\bhereditary peer register\b",
        ),
    )
    if not direct:
        return []
    return [
        item for item in claims
        if re.search(r"\b(?:british|scottish|united kingdom)\b", item.normalized)
    ]


def _rock_music_matches(
    claims: list[Evidence],
    source_evidence: list[Evidence],
) -> list[Evidence]:
    direct = _matching(claims, TOPIC_PATTERNS["Rock music"])
    if direct:
        return direct
    musicians = [
        item for item in claims
        if re.search(
            r"\b(?:is|was) (?:an? )?(?:(?:american|british|irish|french|italian|"
            r"canadian|australian) )?(?:rock )?(?:guitarist|singer|songwriter|musician)\b|"
            r"\b(?:band|group) s (?:guitarist|singer|songwriter)\b",
            item.normalized,
        )
    ]
    if musicians and _matching(source_evidence, (r"\brock(?: and roll)?\b",)):
        return musicians
    return []


def _electronic_dance_music_matches(claims: list[Evidence]) -> list[Evidence]:
    direct = _matching(claims, TOPIC_PATTERNS["Electronic dance music"])
    if direct:
        return direct
    has_dj = any(re.search(r"\bdj\b", item.normalized) for item in claims)
    if not has_dj:
        return []
    return [
        item for item in claims
        if re.search(
            r"\belectronic (?:music|releases?|productions?)\b|"
            r"\belectronic and latin influenced releases\b",
            item.normalized,
        )
    ]


def _royalty_matches(
    dossier: dict[str, Any],
    claims: list[Evidence],
) -> list[Evidence]:
    wealth_origin = dossier.get("wealth_origin")
    relationship = dossier.get("wealth_relationship")
    classified = (
        isinstance(wealth_origin, dict)
        and wealth_origin.get("classification") == "dynastic_royal"
    ) or (
        isinstance(relationship, dict)
        and relationship.get("classification") == "royal_beneficiary"
    )
    if not classified:
        return []
    return [
        item for item in claims
        if ROYAL_CONTEXT_PATTERN.search(item.normalized)
    ]


def _government_owned_matches(
    dossier: dict[str, Any],
    claims: list[Evidence],
) -> list[Evidence]:
    if dossier.get("record_type") != "institution":
        return []
    identity_claims = [
        item for item in claims
        if item.path.startswith((
            "biography.plain_text",
            "long_biography.plain_text",
            "biography_brief.durable_identity",
            "biography_brief.defining_work",
            "editorial_note.plain_text",
        ))
    ]
    explicit = _matching(identity_claims, GOVERNMENT_OWNERSHIP_PATTERNS)
    if explicit:
        return explicit

    owner_name = _normalize(
        str(dossier.get("owner", {}).get("display_name", ""))
    )
    if not GOVERNMENT_OWNER_NAME_PATTERN.search(owner_name):
        return []
    return [
        item for item in identity_claims
        if re.search(
            r"\b(?:government|state administration|public institution|"
            r"public body|municipal|municipality)\b",
            item.normalized,
        )
    ]


def _professional_sports_ownership_matches(
    claims: list[Evidence],
) -> list[Evidence]:
    sport = re.compile(
        r"\b(?:professional sports?|football|soccer|basketball|baseball|ice hockey|"
        r"hockey|american football|nfl|nba|nhl|mlb|formula 1|formula one|nascar|"
        r"motorsport|racing|sports franchise|sports club|buffalo bills|"
        r"buffalo sabres)\b"
    )
    ownership = re.compile(
        r"\b(?:owner|owners|owns|ownership|owned|controlling interest|acquired|bought|"
        r"managing general partner|franchise)\b"
    )
    direct = [
        item for item in claims
        if sport.search(item.normalized) and ownership.search(item.normalized)
        and not re.search(r"\bowner led\b", item.normalized)
    ]
    owner_team = [
        item for item in claims
        if sport.search(item.normalized)
        and re.search(r"\bowner\b.*\bteam\b|\bteam\b.*\bowner\b", item.normalized)
        and not re.search(
            r"\b(?:management|executive|acquisition|operating) team\b",
            item.normalized,
        )
    ]
    explicit = [
        item for item in claims
        if re.search(
            r"\b(?:team ownership|sports? ownership|"
            r"acquired (?:the )?[^.]{0,45} (?:team|club|franchise))\b",
            item.normalized,
        )
    ]
    return list({item.path: item for item in (*direct, *owner_team, *explicit)}.values())


def _direct_source_matches(
    tag: CanonicalTag,
    source_evidence: list[Evidence],
    assignment_patterns: Iterable[str],
) -> list[Evidence]:
    patterns = list(assignment_patterns)
    patterns.extend(_label_pattern(label) for label in (tag.name, *tag.aliases))
    return _matching(source_evidence, patterns)


def _tag_source_ids(
    match: Match,
    dossier: dict[str, Any],
    source_evidence: list[Evidence],
    assignment_patterns: Iterable[str],
) -> tuple[list[str], bool]:
    sources = {
        source.get("id"): source
        for source in dossier.get("sources", [])
        if isinstance(source, dict) and isinstance(source.get("id"), str)
    }
    direct = _direct_source_matches(
        match.tag,
        source_evidence,
        assignment_patterns,
    )
    direct_ids = {
        item.direct_source_id for item in direct if item.direct_source_id is not None
    }
    field_ids = {
        source_id for item in match.evidence for source_id in item.source_ids
    }
    directly_cited = direct_ids & field_ids
    candidates = directly_cited or field_ids
    ordered = sorted(
        (source_id for source_id in candidates if source_id in sources),
        key=lambda source_id: (
            sources[source_id].get("tier", 99),
            list(sources).index(source_id),
        ),
    )
    return ordered[:4], bool(directly_cited)


def _confidence_score(
    dossier: dict[str, Any],
    source_ids: list[str],
    *,
    direct: bool,
) -> int:
    tiers = {
        source.get("id"): source.get("tier")
        for source in dossier.get("sources", [])
        if isinstance(source, dict)
    }
    best_tier = min(
        (
            tier for source_id in source_ids
            if isinstance((tier := tiers.get(source_id)), int)
        ),
        default=4,
    )
    if best_tier <= 2:
        return 92 if direct else 86
    if best_tier == 3:
        return 80
    return 70


def _summary(owner_name: str, tag: CanonicalTag) -> str:
    facets = set(tag.facets)
    if tag.name == "Government-owned":
        return (
            f"The dossier identifies {owner_name} as a government or "
            "state-owned public institution."
        )
    if "royal family" in facets:
        return f"The dossier identifies {owner_name} as a member of {tag.name}."
    if "family" in facets:
        return (
            f"The dossier places {owner_name} within the durable business and "
            f"wealth context of the {tag.name}."
        )
    if facets & {"company", "organisation", "company association"}:
        return (
            f"The dossier documents a material career, ownership, investment or "
            f"family-wealth association between {owner_name} and {tag.name}."
        )
    if "philanthropy" in facets:
        return (
            f"The dossier documents sustained work or giving by {owner_name} in "
            f"{tag.name.lower()}."
        )
    if "sport" in facets:
        return f"The dossier documents {owner_name}'s durable association with {tag.name}."
    if "occupation" in facets:
        return f"The dossier supports {tag.name.lower()} as a durable part of {owner_name}'s career."
    return f"The dossier supports {tag.name} as a durable, material grouping for {owner_name}."


def _confidence(score: int, reason: str) -> dict[str, Any]:
    if score >= 95:
        band = "very_high"
    elif score >= 85:
        band = "high"
    else:
        band = "medium"
    return {"score": score, "band": band, "reason": reason}


def _patterns_for_match(match: Match) -> tuple[str, ...]:
    name = match.tag.name
    facets = set(match.tag.facets)
    if name == "Government-owned":
        return GOVERNMENT_OWNERSHIP_PATTERNS
    if facets & {"company", "organisation", "company association"}:
        return _company_patterns(match.tag)
    if name in TOPIC_PATTERNS:
        return TOPIC_PATTERNS[name]
    if name in PHILANTHROPY_DOMAINS:
        return PHILANTHROPY_DOMAINS[name]
    if name in CONSERVATION_PATTERNS:
        return CONSERVATION_PATTERNS[name]
    return tuple(_label_pattern(label) for label in (name, *match.tag.aliases))


def assign_tags(
    dossier: dict[str, Any],
    catalogue: TagCatalogue,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if dossier.get("record_type") == "unresolved_placeholder":
        return [], []

    claims, source_evidence = build_evidence(dossier)
    matches: dict[str, Match] = {}
    decisions: list[dict[str, Any]] = []

    for tag in catalogue.tags_by_id.values():
        if tag.merged_into is not None:
            continue
        facets = set(tag.facets)
        evidence: list[Evidence] = []
        method = ""
        if "royal family" in facets:
            evidence = _royal_family_matches(tag, dossier, claims)
            method = "royal-family evidence"
        elif "family" in facets:
            evidence = _family_matches(tag, dossier, claims)
            method = "business-family evidence"
        elif facets & {"company", "organisation", "company association"}:
            evidence = _material_company_matches(tag, claims)
            method = "material named-entity association"
        elif tag.name in PHILANTHROPY_DOMAINS:
            evidence = _philanthropy_matches(tag.name, claims)
            method = "philanthropy domain co-occurrence"
        elif tag.name in CONSERVATION_PATTERNS:
            evidence = _matching(claims, CONSERVATION_PATTERNS[tag.name])
            method = "conservation evidence"
        elif tag.name == "Gambling":
            evidence = _gambling_matches(dossier, claims)
            method = "gambling/casino industry evidence"
        elif tag.name == "Government-owned":
            evidence = _government_owned_matches(dossier, claims)
            method = "government/state institutional ownership evidence"
        elif tag.name == "Private equity":
            evidence = _private_equity_matches(claims)
            method = "private-equity role evidence"
        elif tag.name == "Aviation":
            evidence = _aviation_matches(dossier, claims)
            method = "aviation role or industry evidence"
        elif tag.name == "Football":
            evidence = _football_matches(claims)
            method = "association-football evidence"
        elif tag.name == "British peerage":
            evidence = _british_peerage_matches(
                dossier,
                claims,
                source_evidence,
            )
            method = "British peerage evidence"
        elif tag.name == "Rock music":
            evidence = _rock_music_matches(claims, source_evidence)
            method = "rock-music career evidence"
        elif tag.name == "Electronic dance music":
            evidence = _electronic_dance_music_matches(claims)
            method = "electronic-dance-music career evidence"
        elif tag.name == "Royalty":
            evidence = _royalty_matches(dossier, claims)
            method = "royal wealth/status classification"
        elif tag.name == "Professional sports ownership":
            evidence = _professional_sports_ownership_matches(claims)
            method = "sports ownership evidence"
        elif tag.name in TOPIC_PATTERNS:
            evidence = _matching(claims, TOPIC_PATTERNS[tag.name])
            method = "durable topic evidence"

        if evidence:
            matches[tag.id] = Match(tag, tuple(evidence), method)

    by_name = {tag.name: tag for tag in catalogue.tags_by_id.values()}
    royalty_tag = by_name["Royalty"]
    for match in tuple(matches.values()):
        if "royal family" in match.tag.facets:
            matches.setdefault(
                royalty_tag.id,
                Match(
                    royalty_tag,
                    match.evidence,
                    f"implied by {match.tag.name}",
                ),
            )
    for source_name, implied_names in IMPLIED_TAGS.items():
        source_tag = by_name[source_name]
        source_match = matches.get(source_tag.id)
        if source_match is None:
            continue
        for implied_name in implied_names:
            implied_tag = by_name[implied_name]
            matches.setdefault(
                implied_tag.id,
                Match(
                    implied_tag,
                    source_match.evidence,
                    f"implied by {source_name}",
                ),
            )

    owner_name = str(dossier.get("owner", {}).get("display_name", "the owner"))
    proposals: list[dict[str, Any]] = []
    for match in sorted(matches.values(), key=lambda item: item.tag.name.casefold()):
        patterns = _patterns_for_match(match)
        source_ids, direct = _tag_source_ids(
            match,
            dossier,
            source_evidence,
            patterns,
        )
        if not source_ids:
            decisions.append(
                {
                    "tag_id": match.tag.id,
                    "name": match.tag.name,
                    "decision": "excluded",
                    "reason": "No direct dossier source IDs could be attached.",
                    "method": match.method,
                }
            )
            continue
        score = _confidence_score(
            dossier,
            source_ids,
            direct=direct,
        )
        reason = (
            f"The dossier's durable narrative supports this grouping and "
            f"{'the source ledger directly names the association' if direct else 'the cited narrative fields supply direct source IDs'}."
        )
        proposals.append(
            {
                "tag_id": match.tag.id,
                "name": match.tag.name,
                "summary": _summary(owner_name, match.tag),
                "confidence": _confidence(score, reason),
                "source_ids": source_ids,
            }
        )
        decisions.append(
            {
                "tag_id": match.tag.id,
                "name": match.tag.name,
                "decision": "included",
                "method": match.method,
                "evidence_paths": sorted({item.path for item in match.evidence}),
                "source_ids": source_ids,
            }
        )
    return proposals, decisions


def migrate_dossier(
    dossier: dict[str, Any],
    catalogue: TagCatalogue,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_schema = dossier.get("schema_version")
    if source_schema not in SUPPORTED_SOURCE_SCHEMAS:
        raise ValueError(
            "expected schema_version 7 or 8, got "
            f"{source_schema!r}"
        )
    if source_schema == LEGACY_SOURCE_SCHEMA and "proposed_tags" in dossier:
        raise ValueError("source v7 dossier unexpectedly already has proposed_tags")
    if source_schema == TARGET_SCHEMA and not isinstance(
        dossier.get("proposed_tags"),
        list,
    ):
        raise ValueError("source v8 dossier must contain proposed_tags as a list")

    proposals, decisions = assign_tags(dossier, catalogue)
    migrated: dict[str, Any] = {}
    for key, value in dossier.items():
        if key == "schema_version":
            migrated[key] = TARGET_SCHEMA
        elif key == "proposed_tags":
            migrated[key] = proposals
        else:
            migrated[key] = value
        if source_schema == LEGACY_SOURCE_SCHEMA and key == "proposed_socials":
            migrated["proposed_tags"] = proposals
    if "proposed_tags" not in migrated:
        migrated["proposed_tags"] = proposals

    if source_schema == TARGET_SCHEMA:
        original_without_tags = {
            key: value for key, value in dossier.items() if key != "proposed_tags"
        }
        migrated_without_tags = {
            key: value for key, value in migrated.items() if key != "proposed_tags"
        }
        if migrated_without_tags != original_without_tags:
            raise ValueError("schema-v8 refresh changed fields other than proposed_tags")

    errors, warnings = validate(migrated)
    if errors:
        raise ValueError("; ".join(errors))
    person_id = migrated.get("owner", {}).get("person_id")
    if not isinstance(person_id, int):
        raise ValueError("owner.person_id must be an integer")
    resolve_dossier_tags(migrated, catalogue, person_id=person_id)
    return migrated, [*decisions, *({"warning": warning} for warning in warnings)]


def _safe_backup_path(directory: Path, requested: Path | None) -> Path:
    owner_research_root = (REPO_ROOT / "output" / "owner-research").resolve()
    if requested is None:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        requested = directory.with_name(f"{directory.name}-tag-backup-{timestamp}")
    resolved = requested.resolve()
    if not resolved.is_relative_to(owner_research_root):
        raise ValueError(
            f"backup path must stay within {owner_research_root}: {resolved}"
        )
    if resolved == directory.resolve() or resolved == owner_research_root:
        raise ValueError("backup path cannot be the dossier directory or output root")
    if resolved.exists():
        raise ValueError(f"backup path already exists: {resolved}")
    return resolved


def _load_and_migrate(
    directory: Path,
    catalogue: TagCatalogue,
) -> tuple[list[tuple[Path, dict[str, Any], dict[str, Any]]], dict[str, Any]]:
    paths = sorted(directory.glob("*.research.json"))
    if not paths:
        raise ValueError(f"no *.research.json files found in {directory}")

    migrated: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    tag_counts: Counter[str] = Counter()
    existing_tag_counts: Counter[str] = Counter()
    added_tag_counts: Counter[str] = Counter()
    removed_tag_counts: Counter[str] = Counter()
    source_schema_counts: Counter[int] = Counter()
    owner_rows: list[dict[str, Any]] = []
    warning_count = 0
    for path in paths:
        try:
            original = json.loads(path.read_text(encoding="utf-8"))
            target, decisions = migrate_dossier(original, catalogue)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
        included = [
            item for item in decisions if item.get("decision") == "included"
        ]
        existing_tags = original.get("proposed_tags", [])
        existing_names = [
            item.get("name")
            for item in existing_tags
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        ]
        target_names = [item["name"] for item in included]
        existing_name_set = set(existing_names)
        target_name_set = set(target_names)
        added_names = sorted(target_name_set - existing_name_set, key=str.casefold)
        removed_names = sorted(existing_name_set - target_name_set, key=str.casefold)
        tag_set_changed = bool(added_names or removed_names)
        document_changed = original != target

        warning_count += sum("warning" in item for item in decisions)
        source_schema_counts.update([original["schema_version"]])
        existing_tag_counts.update(existing_names)
        tag_counts.update(target_names)
        added_tag_counts.update(added_names)
        removed_tag_counts.update(removed_names)
        owner_rows.append(
            {
                "person_id": target["owner"]["person_id"],
                "display_name": target["owner"]["display_name"],
                "record_type": target["record_type"],
                "source_schema_version": original["schema_version"],
                "document_changed": document_changed,
                "tag_set_changed": tag_set_changed,
                "existing_tag_ids": [
                    item.get("tag_id")
                    for item in existing_tags
                    if isinstance(item, dict)
                ],
                "existing_tag_names": existing_names,
                "tag_ids": [item["tag_id"] for item in included],
                "tag_names": target_names,
                "added_tag_names": added_names,
                "removed_tag_names": removed_names,
                "decisions": decisions,
            }
        )
        migrated.append((path, original, target))

    count_rows = []
    all_names = sorted(
        {
            tag.name
            for tag in catalogue.tags_by_id.values()
            if tag.merged_into is None
        }
        | set(existing_tag_counts),
        key=str.casefold,
    )
    for name in all_names:
        actual = tag_counts.get(name, 0)
        before = existing_tag_counts.get(name, 0)
        prior = PRIOR_REVIEW_COUNTS.get(name)
        count_rows.append(
            {
                "name": name,
                "before_count": before,
                "applicable_count": actual,
                "change": actual - before,
                "added_assignments": added_tag_counts.get(name, 0),
                "removed_assignments": removed_tag_counts.get(name, 0),
                "prior_review_count": prior,
                "difference": actual - prior if prior is not None else None,
            }
        )

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "dry-run",
        "dossier_directory": str(directory.resolve()),
        "catalogue": catalogue.source_reference,
        "source_schema_version_counts": {
            str(version): count
            for version, count in sorted(source_schema_counts.items())
        },
        "target_schema_version": TARGET_SCHEMA,
        "dossier_count": len(migrated),
        "record_type_counts": dict(
            sorted(Counter(item[2]["record_type"] for item in migrated).items())
        ),
        "owners_with_tags": sum(bool(row["tag_ids"]) for row in owner_rows),
        "owners_without_tags": sum(not row["tag_ids"] for row in owner_rows),
        "owners_with_document_changes": sum(
            row["document_changed"] for row in owner_rows
        ),
        "owners_unchanged": sum(
            not row["document_changed"] for row in owner_rows
        ),
        "owners_with_tag_set_changes": sum(
            row["tag_set_changed"] for row in owner_rows
        ),
        "owners_with_metadata_only_changes": sum(
            row["document_changed"] and not row["tag_set_changed"]
            for row in owner_rows
        ),
        "existing_total_tag_assignments": sum(existing_tag_counts.values()),
        "total_tag_assignments": sum(tag_counts.values()),
        "added_tag_assignments": sum(added_tag_counts.values()),
        "removed_tag_assignments": sum(removed_tag_counts.values()),
        "validator_warning_count": warning_count,
        "tag_counts": count_rows,
        "owners": owner_rows,
    }
    return migrated, report


def _write_audit(path: Path, report: dict[str, Any]) -> None:
    atomic_write_json(path, report)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Assign conservative dossier-supported owner tags, migrating "
            "completed schema-v7 dossiers or refreshing schema-v8 dossiers. "
            "Dry-run is the default; --apply makes an exact backup before "
            "atomic writes."
        )
    )
    parser.add_argument("directory", nargs="?", type=Path, default=DEFAULT_DOSSIER_DIR)
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    directory = args.directory.resolve()
    if not directory.is_dir():
        print(f"ERROR: dossier directory does not exist: {directory}", file=sys.stderr)
        return 1

    try:
        catalogue = load_tag_catalogue(args.catalogue.resolve())
        migrated, report = _load_and_migrate(directory, catalogue)
        backup_path: Path | None = None
        if args.apply:
            backup_path = _safe_backup_path(directory, args.backup_dir)
            backup_path.mkdir(parents=True)
            for path, _, _ in migrated:
                shutil.copy2(path, backup_path / path.name)
            if len(list(backup_path.glob("*.research.json"))) != len(migrated):
                raise ValueError("backup verification count does not match source count")
            mismatches = [
                path.name
                for path, _, _ in migrated
                if not filecmp.cmp(
                    path,
                    backup_path / path.name,
                    shallow=False,
                )
            ]
            if mismatches:
                raise ValueError(
                    "byte-for-byte backup verification failed for: "
                    + ", ".join(mismatches[:10])
                )
            changed = [item for item in migrated if item[1] != item[2]]
            for path, _, target in changed:
                atomic_write_json(path, target)
            for path, _, target in changed:
                written = json.loads(path.read_text(encoding="utf-8"))
                if written != target:
                    raise ValueError(
                        f"post-write verification differs from target: {path.name}"
                    )
                errors, _ = validate(written)
                if errors:
                    raise ValueError(
                        f"post-write dossier validation failed for {path.name}: "
                        + "; ".join(errors)
                    )
                resolve_dossier_tags(
                    written,
                    catalogue,
                    person_id=written["owner"]["person_id"],
                )
            report["mode"] = "applied"
            report["backup_directory"] = str(backup_path)
            report["backup_verified_byte_for_byte"] = True
            report["written_dossier_count"] = len(changed)
            report["written_dossiers_verified"] = True
        if args.audit_output is not None:
            _write_audit(args.audit_output.resolve(), report)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"{report['mode']}: {report['dossier_count']} dossiers; "
        f"{report['owners_with_tags']} with tags; "
        f"{report['total_tag_assignments']} assignments; "
        f"{report['validator_warning_count']} validator warnings"
    )
    if args.apply:
        print(f"Backup: {report['backup_directory']}")
    if args.audit_output is not None:
        print(f"Audit: {args.audit_output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

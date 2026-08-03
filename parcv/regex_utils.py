import re

EMAIL_REGEX = re.compile(
    r'[\w.+-]+@[\w-]+\.[\w.-]+',
    re.IGNORECASE
)
PHONE_REGEX = re.compile(
    r"(?:\+?1[\s\-\.]*)?\(?\d{3}\)?[\s\-\.]*\d{3}[\s\-\.]*\d{4}|"  # NA Formats
    r"(?:\+62|62|0)[\s\-\.]*8\d{1,2}[\s\-\.]*\d{3,4}[\s\-\.]*\d{3,5}|"  # Indonesian Formats
    r"(?:\+|00)\d{1,3}[\s\-\.]*(?:\(\d{1,4}\))?[\s\-\.]*\d{1,4}[\s\-\.]*\d{1,4}[\s\-\.]*\d{1,4}",  # International Formats
    re.IGNORECASE
)
MONTHS = (
    r"Jan(?:uary|uari)?|Feb(?:ruary|ruari)?|Mar(?:ch|et)?|Apr(?:il)?|May|Mei|"
    r"Jun(?:e|i)?|Jul(?:y|i)?|Aug(?:ust)?|Agustus|Sep(?:t(?:ember)?)?|"
    r"Oct(?:ober)?|Okt(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|Des(?:ember)?"
)

MONTH_YEAR_REGEX = re.compile(
    rf'\b(?:{MONTHS})\s+\d{{4}}\b',
    re.IGNORECASE
)

YEAR_REGEX = re.compile(
    r'\b(?:19|20)\d{2}\b'
)

DATE_RANGE_REGEX = re.compile(
    rf'''
    (
        (?:
            (?:{MONTHS})\s+\d{{4}}
            |
            \d{{4}}
        )
    )

    \s*(?:-|–|—|to|sampai|hingga)\s*

    (
        (?:
            (?:{MONTHS})\s+\d{{4}}
            |
            \d{{4}}
            |
            Present
            |
            Current
            |
            Now
            |
            Sekarang
            |
            Saat\s+ini
        )
    )
    ''',
    re.IGNORECASE | re.VERBOSE
)

SCHOOL_REGEX = re.compile(
    r'''
    \b(
        University|
        College|
        School|
        Institute|
        Academy|
        Polytechnic|
        Universitas|
        Sekolah|
        Institut|
        Akademi|
        Politeknik
    )\b
    ''',
    re.IGNORECASE | re.VERBOSE
)
DEGREE_REGEX = re.compile(
    r'''
    \b(
        Bachelor|Master|Associate|Doctor|PhD|BSc|BA|BS|MSc|MA|MBA|MEarthSci|GCSE|A\s?levels?|
        Sarjana|Diploma|SMA|SMK|S1|S2|S3|Magister|Doktor
    )
    ''',
    re.IGNORECASE | re.VERBOSE
)
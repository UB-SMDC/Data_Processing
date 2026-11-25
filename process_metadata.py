"""

Install: pip install pandas requests pymupdf
Run: python process_insitu_metadata.py
Modified: 11.25.2026

"""
from pathlib import Path
from urllib.parse import unquote, urlparse
import re
import time

import fitz
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

INPUT_CSV = Path('metadata_Insitu_Compeleted.csv')
OUTPUT_CSV = Path('metadata_Insitu_Compeleted_enriched.csv')
PDF_DIR = Path('Insitu_Compeleted_pdf_by_uuid')
BASE_URL = 'https://ubsmdc.sfb1502.de/geonetwork/srv/api/records/'
PDF_DIR.mkdir(exist_ok=True)

UUID_RE = re.compile(r'^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$', re.I)
FIELD_RE = re.compile(
    r'^(?:Data\s+provider\s*\(\s*Data\s+cent(?:er|re)\s*\)|'
    r'Source\s*/\s*Provider)\s*:?\s*(.*)$',
    re.I
)

STOP_FIELDS = [
    'Native data format', 'Temporal extent', 'Temporal resolution',
    'Country, Location', 'Spatial extent', 'SMC variables',
    'DOI', 'Overview', 'User guide', 'Download Options',
    'Use constraints', 'Description', 'Data Sample',
]
STOP_RE = re.compile(r'^(?:' + '|'.join(re.escape(x) for x in STOP_FIELDS) + r')\b', re.I)
ROLE_RE = re.compile(r'\b(originator|ordinator|manager|provider|producer|creator|distributor|archiver|publisher)\b', re.I)
PROVIDER_ROLES = {'originator', 'ordinator', 'manager', 'provider', 'producer', 'creator'}
DISTRIBUTOR_ROLES = {'distributor', 'archiver', 'publisher'}

session = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('http://', HTTPAdapter(max_retries=retry))
session.mount('https://', HTTPAdapter(max_retries=retry))


def split_links(value):
    if pd.isna(value):
        return []
    return [part.strip() for part in str(value).split('###') if part.strip()]


def find_attachment(links, uuid):
    # Some other links point to unrelated PDFs (e.g. a readme).
    candidates = []
    for link in links:
        clean = unquote(link).replace('\\(', '(').replace('\\)', ')')
        if '/attachments/' in clean.lower() and re.search(r'\.pdf(?:[?#]|$)', clean, re.I):
            candidates.append(clean)
    return next((x for x in candidates if uuid.lower() in x.lower()), candidates[0] if candidates else '')


def download_pdf(url, path):
    if path.exists() and path.stat().st_size > 0:
        try:
            with fitz.open(path) as doc:
                if doc.page_count:
                    return 'cached'
        except Exception:
            path.unlink(missing_ok=True)
    with session.get(url, timeout=(10, 45), stream=True) as response:
        response.raise_for_status()
        with path.open('wb') as out:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    out.write(chunk)
    try:
        with fitz.open(path) as doc:
            if not doc.page_count:
                raise ValueError('PDF has no pages')
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return 'downloaded'


def provider_field(pdf_path):
    with fitz.open(pdf_path) as doc:
        # Page 2 contains the table in the example. Search every page for safety.
        for page in doc:
            lines = [re.sub(r'\s+', ' ', x).strip() for x in page.get_text(sort=True).splitlines()]
            for i, line in enumerate(lines):
                found = FIELD_RE.match(line)
                if not found:
                    continue
                values = [found.group(1)] if found.group(1) else []
                for subsequent in lines[i + 1:]:
                    if STOP_RE.match(subsequent):
                        break
                    if subsequent:
                        values.append(subsequent)
                return ' '.join(values).strip()
    return ''


def split_organizations(field):
    """Split after a parenthesized role list, not at arbitrary commas.

    Example: University of California, Berkeley (Ordinator, Manager),
             ISMN (International soil moisture network) (Archiver, Distributor)
    """
    # Match the LAST parenthetical group when it contains role keywords.
    role_group = re.compile(r'\(([^()]*)\)')
    organizations = []
    start = 0
    for match in role_group.finditer(field):
        roles = {r.lower() for r in ROLE_RE.findall(match.group(1))}
        if not roles:
            continue
        name = field[start:match.start()].strip(' ,;\n')
        if name:
            organizations.append((name, roles))
        start = match.end()
    return organizations


def extract_roles(pdf_path):
    field = provider_field(pdf_path)
    if not field:
        return '', '', 'field not found'
    groups = split_organizations(field)
    if not groups:
        return '', '', 'roles not recognized'
    providers = list(dict.fromkeys(name for name, roles in groups if roles & PROVIDER_ROLES))
    distributors = list(dict.fromkeys(name for name, roles in groups if roles & DISTRIBUTOR_ROLES))
    # Preserve the original field separately for auditing ambiguous role labels.
    return ' | '.join(providers), ' | '.join(distributors), 'parsed'


def main():
    # File has Latin-1 bytes and >16,000 completely empty trailing columns.
    df = pd.read_csv(INPUT_CSV, encoding='latin1', dtype=str, low_memory=False)
    df = df.dropna(axis=1, how='all')
    if not {'uuid', 'link'}.issubset(df.columns):
        raise ValueError('CSV must contain columns named uuid and link')

    links_by_row = df['link'].apply(split_links)
    max_links = max((len(x) for x in links_by_row), default=0)
    df['metadata Link'] = df['uuid'].fillna('').apply(
        lambda x: BASE_URL + x.strip() if UUID_RE.fullmatch(x.strip()) else ''
    )
    for i in range(max_links):
        df[f'link_{i + 1}'] = links_by_row.apply(lambda x: x[i] if len(x) > i else '')

    providers, distributors, fields, pdf_urls, statuses = [], [], [], [], []
    for index, (uuid, links) in enumerate(zip(df['uuid'].fillna(''), links_by_row), start=1):
        uuid = uuid.strip()
        url = find_attachment(links, uuid)
        pdf_urls.append(url)
        if not UUID_RE.fullmatch(uuid):
            providers.append(''); distributors.append(''); fields.append(''); statuses.append('invalid UUID')
            continue
        if not url:
            providers.append(''); distributors.append(''); fields.append(''); statuses.append('no attachment PDF link')
            continue
        try:
            file_path = PDF_DIR / f'{uuid}.pdf'
            download_state = download_pdf(url, file_path)
            field = provider_field(file_path)
            p, d, parse_state = extract_roles(file_path)
            providers.append(p); distributors.append(d); fields.append(field)
            statuses.append(f'{download_state}; {parse_state}')
        except Exception as exc:
            providers.append(''); distributors.append(''); fields.append('')
            statuses.append(f'ERROR: {type(exc).__name__}: {str(exc)[:160]}')
        print(f'[{index}/{len(df)}] {uuid}: {statuses[-1]}', flush=True)
        if 'downloaded' in statuses[-1]:
            time.sleep(0.2)

    df['PDF attachment link'] = pdf_urls
    df['data Providers'] = providers
    df['data Distributor'] = distributors
    df['data provider raw field'] = fields
    df['PDF status'] = statuses
    df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    print(f'Finished: {OUTPUT_CSV} | rows={len(df)} | link columns={max_links}')
    print(pd.Series(statuses).value_counts().to_string())


if __name__ == '__main__':
    main()

"""Text-only target/event parsing. This module never reads benchmark metadata."""
import re

VISIBLE_FIELDS = ('question', 'option_A', 'option_B', 'option_C', 'option_D', 'statement_A', 'statement_B')
EVENT_RULES = {
    'fully_hidden': r'\bfully\s+(?:hidden|blocked|occluded)\b',
    'partly_hidden': r'\b(?:partly|partially)\s+(?:hidden|blocked|occluded)\b',
    'comes_back_into_view': r'\b(?:comes?|coming)\s+back(?:\s+into\s+view)?\b',
    'leaves_frame': r'\b(?:leaves?|left|leaving)\s+the\s+frame\b',
    'disappears': r'\bdisappears?\b',
    'changes_abruptly': r'\bchanges?\s+abruptly\b',
    'enters_frame': r'\benters?\s+the\s+frame\b',
    'first_shows_up': r'\bfirst\s+shows?\s+up\b',
}
EXPRESSIBLE = {'fully_hidden', 'comes_back_into_view', 'leaves_frame', 'disappears', 'enters_frame', 'first_shows_up'}
SUBJECT_QUESTION_RULES = [
    r'^How many times (?:does|do) (.+?) (?:get|come|change|leave|disappear|enter)\b',
    r'^How many times is (.+?) (?:partly|fully) hidden\b',
    r'^(?:Before|When|After) (.+?) (?:comes? back into view|disappears)\b',
    r'^Put the following events for (.+?) in order from earliest to latest',
]
CLAUSE_SUBJECT = re.compile(r'^(.*?)\s+(?:gets?|got|was|is|leaves?|left|comes?|coming|disappears?|changes?|enters?|first shows? up)\b', re.I)


def visible_texts(item):
    texts = [(key, item[key]) for key in VISIBLE_FIELDS if item.get(key)]
    texts += [('event_' + event['label'], event['event_text']) for event in item.get('events', [])]
    return texts


def clean_phrase(text):
    text = re.sub(r'\s+', ' ', text.lower()).strip(' ,.?"')
    text = re.sub(r'^(?:the|an|a)\s+', '', text)
    return re.sub(r'\s+that$', '', text).strip()


def question_subject(question):
    for pattern in SUBJECT_QUESTION_RULES:
        match = re.search(pattern, question, re.I)
        if match:
            return clean_phrase(match.group(1))
    return None


def extract_targets(item):
    primary = question_subject(item['question'])
    candidates = [primary] if primary else []
    provenance = [{'field': 'question', 'phrase': primary}] if primary else []
    for field, text in visible_texts(item):
        if field == 'question':
            continue
        for clause in re.split(r'\s+(?:before|after)\s+', text, flags=re.I):
            match = CLAUSE_SUBJECT.search(clause.strip())
            if not match:
                continue
            phrase = clean_phrase(match.group(1))
            if phrase in ('it', 'they', 'them'):
                phrase = primary
            if phrase:
                candidates.append(phrase)
                provenance.append({'field': field, 'phrase': phrase})
    queries = []
    for phrase in candidates:
        # ReID statements shorten "red cap" to "cap"; retain the question's
        # more specific referent. Cross-object questions have no such primary.
        if primary and (primary.endswith(' ' + phrase) or primary.startswith(phrase + ' in ')):
            phrase = primary
        if phrase not in queries:
            queries.append(phrase)
    return dict(queries=queries, primary_question_subject=primary, provenance=provenance,
                method='visible-text template parser v1; no metadata input')


def event_types(text):
    return [name for name, pattern in EVENT_RULES.items() if re.search(pattern, text, re.I)]


def required_events(item):
    """Return subject-predicate pairs in the actual question/alternatives."""
    primary = question_subject(item['question'])
    records = []
    for field, text in visible_texts(item):
        if field == 'question':
            if primary:
                for kind in event_types(text):
                    records.append(dict(query=primary, event_type=kind, field=field, text=text))
            continue
        for clause in re.split(r'\s+(?:before|after)\s+', text, flags=re.I):
            match = CLAUSE_SUBJECT.search(clause.strip())
            subject = clean_phrase(match.group(1)) if match else None
            if subject in ('it', 'they', 'them'):
                subject = primary
            if primary and subject and (primary.endswith(' ' + subject) or primary.startswith(subject + ' in ')):
                subject = primary
            for kind in event_types(clause):
                records.append(dict(query=subject or primary, event_type=kind, field=field, text=clause))
    return records


def classify(item):
    kinds = sorted({kind for _, text in visible_texts(item) for kind in event_types(text)})
    if not kinds:
        kinds = ['other']
    blocked = sorted(set(kinds) - EXPRESSIBLE)
    return dict(event_types=kinds, trackable=not blocked,
                exclusion_reasons=blocked, events=required_events(item))


def normalize_for_evaluation(text):
    text = re.sub(r'[^a-z0-9\s]', ' ', text.lower())
    return ' '.join(word for word in text.split() if word not in ('a', 'an', 'the'))

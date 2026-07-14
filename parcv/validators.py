import re

def strip_prefixes(skill):
    skill = skill.strip()
    skill = re.sub(r'^(?i)(and\s+|with\s+|in\s+|to\s+|of\s+|for\s+)', '', skill)
    skill = re.sub(r'^[^a-zA-Z0-9]+', '', skill)
    return skill.strip()

def strip_suffixes(skill):
    skill = skill.strip()
    skill = re.sub(r'[^a-zA-Z0-9\+]+$', '', skill)
    return skill.strip()

def clean_skill(skill):
    if not skill:
        return ""
    skill = strip_prefixes(skill)
    skill = strip_suffixes(skill)
    return skill

def is_valid_skill(skill):
    if not skill:
        return False
    words = skill.split()
    if not (0 < len(words) <= 5):
        return False
    if skill.lower() in {"and", "the", "with", "etc", "skills", "other", "proficient"}:
        return False
    return True

def remove_duplicates(skills):
    seen = set()
    unique_skills = []
    for skill in skills:
        lower_skill = skill.lower()
        if lower_skill not in seen:
            seen.add(lower_skill)
            unique_skills.append(skill)
    return unique_skills

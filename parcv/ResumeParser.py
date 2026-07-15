from tracemalloc import start
from matplotlib.pyplot import contour
from parcv.Models import Models
from datetime import datetime
from dateutil import parser
import re
from string import punctuation
from collections import Counter
from parcv.regex_utils import *
from parcv.validators import *
import math

class ResumeParser:

    def __init__(self, ner, ner_dates, zero_shot_classifier, tagger, qa_squad):
        self.models = Models()
        self.ner, self.ner_dates, self.zero_shot_classifier, self.tagger, self.qa_squad = ner, ner_dates, zero_shot_classifier, tagger, qa_squad
        self.parsed_cv = {}

    def parse(self, resume_segments):
        for segment_name in resume_segments:
            resume_segment = resume_segments[segment_name]
            if segment_name == "contact_info":
                self.new_parse_contact_info(resume_segment)
            elif segment_name == "work_and_employment":
                self.new_parse_job_history(resume_segment)
            elif segment_name == "education_and_training":
                self.parse_education_history(resume_segment)
            elif segment_name == "skills":
                self.parse_skills(resume_segment)
        return self.parsed_cv
    
    def parse_skills(self, resume_segment):
        splitter = re.compile(r'[,;\|\•\:\(\)]+')
        labels = ['technical skill', 'skill', 'other']
        skills = []
        for item in resume_segment:
            if ':' in item:
                item = item.split(':', 1)[1]
            for elem in splitter.split(item):
                candidate_skill = clean_skill(elem)
                if is_valid_skill(candidate_skill):
                    if self.belongs_to_label(candidate_skill, 'technical skill', labels) or self.belongs_to_label(candidate_skill, 'skill', labels):
                        skills.append(candidate_skill)
        self.parsed_cv['Skills'] = remove_duplicates(skills)

    def parse_education_history(self, resume_segment):
        self.parsed_cv["Education"] = []
        education_info = []
        idx_schools = self.find_school_names(resume_segment)
        if not idx_schools: return
        for i, (idx, school_name) in enumerate(idx_schools):
            education_item = {'School Name': school_name, 'Field of Study': '', 'Qualification': ''}
            start_idx = 0 if i == 0 else idx
            end_idx = idx_schools[i+1][0] if i + 1 < len(idx_schools) else len(resume_segment)
            chunk = " , ".join(resume_segment[start_idx:end_idx])
            qa_input_major = {'question': "what is the field of study or major?", 'context': chunk}
            major = self.qa_squad(qa_input_major)['answer']
            qa_input_qual = {'question': "what is the qualification or degree?", 'context': chunk}
            qual = self.qa_squad(qa_input_qual)['answer']
            education_item['Field of Study'] = major.strip(" ,.;:-") if major else ""
            education_item['Qualification'] = qual.strip(" ,.;:-") if qual else ""
            education_info.append(education_item)
        self.parsed_cv["Education"] = education_info
        

    def get_closest_item_to_school(self, items, right_position, idx, idx1, idx2):
        closest_left = math.inf
        closest_left_item = None
        closest_right = math.inf
        closest_right_item = None
        for item in items:
            st_idx, end_idx = item[1]
            if end_idx <= idx1:
                if idx1 - end_idx < closest_left:
                    closest_left = idx1 - end_idx
                    closest_left_item = item
            elif st_idx >= idx2:
                if st_idx - idx2 < closest_right:
                    closest_right = st_idx - idx2
                    closest_right_item = item
        if idx == 0:
            if closest_right < closest_left: right_position = True
            else: right_position = False

        if right_position:
            if closest_right_item:
                return closest_right_item, right_position
            elif closest_left_item:
                return closest_left_item, right_position
        else:
            if closest_left_item:
                return closest_left_item, right_position
            elif closest_right_item:
                return closest_right_item, right_position
        return "", right_position


    def ask_till_stopping(self, resume_segment, question, category, limit):
        labels = ['school name', 'field of study', 'degree', "location", "other"]
        context = ' , '.join(resume_segment)
        answer_idxs = [] 
        if not context.strip(): return answer_idxs
        while True:
            qa_input = {'question': question, 'context': context}
            out = self.qa_squad(qa_input)
            start_idx, end_idx, answer = out['start'], out['end'], out['answer']
            if not answer:
                break
            context = context.replace(context[start_idx:end_idx], "")
            if not context.strip(): return answer_idxs
            splitter = re.compile(r'[\s{}]+'.format(re.escape(punctuation)))
            answer_splitted = splitter.split(answer)
            answer_splitted = [i for i in answer_splitted if i and not i.isdigit() and i.isalpha() ]
            capitalized = all([True if i[0].isupper() else False for i in answer_splitted])
            if len(answer_splitted) > 2:
                num_of_1 = sum([True if i[0].isupper() else False for i in answer_splitted])
                capitalized = num_of_1 > len(answer_splitted)//2
            if not capitalized:
                break
            else:
                if category == 'school name':
                    if self.belongs_to_label(answer, category, labels):
                        answer_idxs.append([answer, (start_idx, end_idx)])
                else:
                    answer_idxs.append([answer, (start_idx, end_idx)])
            if len(answer_idxs) > limit:
                break
        return answer_idxs

    def new_find_person_name(self, contact_info):
        context = ' '.join(contact_info[:3])
        ner_results = self.ner(context)
        for entity in ner_results:
            if entity.get('entity_group', '') == 'PER' or entity.get('entity', '') == 'PER':
                name = entity['word'].title().strip(" ,.;:-")
                if len(name) > 1:
                    return name
        qa_input = {'question': "What is the full name of the candidate?", 'context': context}
        answer = self.qa_squad(qa_input)['answer']
        if answer and len(answer.split()) == 1:
            words = context.split()
            clean_words = [w.strip(" ,.;:-") for w in words]
            clean_answer = answer.strip(" ,.;:-")
            
            try:
                idx = clean_words.index(clean_answer)
                if idx + 1 < len(words) and not any(char in words[idx+1] for char in ":@|"):
                    answer = f"{answer.strip()} {words[idx+1].strip(' ,.;:-')}"
            except ValueError:
                pass
                
        return answer.title().strip(" ,.;:-") if answer else ""


    def find_school_names(self, resume_segment):
        idx_line = []
        # SHIELD: Block common academic filler that the AI mistakes for universities
        exclusion_words = ['honor', 'list', 'award', 'gpa', 'project', 'team', 'club']
        for idx, line in enumerate(resume_segment):
            line_lower = line.lower()
            if any(word in line_lower for word in exclusion_words):
                continue
            if SCHOOL_REGEX.search(line):
                qa_input = {'question': "What is the name of the university or college?", 'context': line}
                answer = self.qa_squad(qa_input)['answer']
                if answer:
                    idx_line.append((idx, answer))
                else:
                    idx_line.append((idx, line.strip()))
                continue
            splitter = re.compile(r'[\s{}]+'.format(re.escape(punctuation)))
            answer_splitted = [i for i in splitter.split(line) if i and not i.isdigit() and i.isalpha()]
            if not answer_splitted: continue
            num_caps = sum(1 for i in answer_splitted if i[0].isupper())
            if num_caps < len(answer_splitted) // 4: continue
            qa_input = {'question': "What is the school's name?", 'context': line}
            answer = self.qa_squad(qa_input)['answer']
            if answer and len(answer.split()) < 7:
                labels = ["school name", "university", "degree", "field of study", "other"]
                res = self.zero_shot_classifier(answer, labels)
                highest = res["labels"][0]
                if highest in ["school name", "university"]:
                    idx_line.append((idx, answer))
        unique_idx_line = []
        seen_idx = set()
        seen_names = set()
        for idx, ans in idx_line:
            ans_lower = ans.lower().strip(" ,.;:-")
            if idx not in seen_idx and ans_lower not in seen_names:
                unique_idx_line.append((idx, ans))
                seen_idx.add(idx)
                seen_names.add(ans_lower)
        return unique_idx_line
    
    def find_job_titles(self, resume_segment):
        labels = ["company", "institution", "job title", "details", "volunteer role"]
        idx_line = []
        for idx, line in enumerate(resume_segment):
            
            # 1. LENGTH SHIELD: Reject long bullet points (over 12 words)
            if len(line.split()) > 12:
                continue
                
            # 2. QUICK CASING SHIELD: Instantly reject completely lowercase lines
            if line.islower():
                continue

            splitter = re.compile(r'[\s{}]+'.format(re.escape(punctuation)))
            answer_splitted = [i for i in splitter.split(line) if i and not i.isdigit() and i.isalpha()]
            if not answer_splitted: continue
            # 3. STRONG CASING SHIELD: At least 50% of the words must be capitalized
            # (This accounts for conjunctions like 'and', 'of', 'dan', 'di' being lowercase)
            num_caps = sum(1 for i in answer_splitted if i[0].isupper())
            if num_caps <= len(answer_splitted) / 2: 
                continue
            qa_input = {'question': "What is the job role or title?", 'context': line}
            out = self.qa_squad(qa_input)
            answer = out['answer']
            res = self.zero_shot_classifier(line, labels)
            highest = res["labels"][0]
            if highest in ["job title", "volunteer role"]:
                if answer:
                    idx_line.append((idx, answer))

        return idx_line

    def belongs_to_label(self, sequence, label, labels):
        res = self.zero_shot_classifier(sequence, labels)
        class_score = zip(res["labels"], res["scores"])
        highest = sorted(class_score, key=lambda x: x[1])[-1]
        if highest[0] == label:
            return True
        return False

    def new_parse_contact_info(self, contact_info):
        contact_info_dict = {}
        name = self.new_find_person_name(contact_info)
        email = self.find_contact_email(contact_info)
        context = " ".join(contact_info)
        phones = self.find_phone_numbers(contact_info)
        contact_info_dict["phone1"] = phones[0] if len(phones) else ""
        contact_info_dict["phone2"] = phones[1] if len(phones) > 1 else ""
        phones = list(dict.fromkeys([p.strip() for p in phones if p.strip()]))
        phone1 = phones[0] if len(phones) > 0 else ""
        phone2 = phones[1] if len(phones) > 1 else ""
        address = self.find_address(contact_info)
        contact_info_dict["Email"] = email.strip(" ,.;:-") if email else ""
        contact_info_dict["phone1"] = phone1
        contact_info_dict["phone2"] = phone2
        contact_info_dict["address"] = address.strip(" ,.;:-") if address else ""
        self.parsed_cv["Name"] = name
        self.parsed_cv["Contact Info"] = contact_info_dict

    def find_phone_numbers(self, items):
        print("\n========== PHONE DEBUG ==========")
        phones = []

        for line in items:
            print("LINE:", repr(line))
            matches = list(PHONE_REGEX.finditer(line))
            print("MATCHES:", [m.group() for m in matches])
            for match in matches:
                phones.append(match.group().strip())
        print("FOUND:", phones)

        return phones

    def find_address(self, contact_info):
        context = ' , '.join(contact_info)
        qa_input = {'question': "What is the address?", 'context': context}
        address = self.qa_squad(qa_input)['answer']
        labels = ['address', 'email', 'phone number', 'other']
        if self.belongs_to_label(address, "address",labels):
            return address
        else: 
            return ""

    def parse_contact_info(self, contact_info):
        contact_info_dict = {}
        name = self.find_person_name(contact_info)
        email = self.find_contact_email(contact_info)
        self.parsed_cv['Name'] = name
        contact_info_dict["Email"] = email
        self.parsed_cv['Contact Info'] = contact_info_dict

    def find_person_name(self, items):
        class_score = []
        splitter = re.compile(r'[{}]+'.format(re.escape(punctuation.replace("&", "") )))
        classes = ["person name", "address", "email", "title"]
        for item in items: 
            elements = splitter.split(item)
            for element in elements:
                element = ''.join(i for i in element.strip() if not i.isdigit())
                if not len(element.strip().split()) > 1: continue
                out = self.zero_shot_classifier(element, classes)
                highest = sorted(zip(out["labels"], out["scores"]), key=lambda x: x[1])[-1]
                if highest[0] == "person name":
                    class_score.append((element, highest[1]))
        if len(class_score):
            return sorted(class_score, key=lambda x: x[1], reverse=True)[0][0]
        return ""
    
    def find_contact_email(self, items):
        for item in items: 
            match = EMAIL_REGEX.search(item)
            if match:
                return match.group(0)
        return ""

    def new_get_job_company(self, line1, line2, resume_segment):
        context = resume_segment[line1]
        if line2 <= len(resume_segment)-1:
            context = context + " , " + resume_segment[line2]
        qa_input = {'question': "What is the company's name?", 'context': context}
        out = self.qa_squad(qa_input)
        return out['answer']



    def new_parse_job_history(self, resume_segment):
        idx_job_title = self.find_job_titles(resume_segment)
        current_and_below = False
        if not len(idx_job_title): 
            self.parsed_cv["Job History"] = [] 
            return
        if idx_job_title[0][0] == 0: current_and_below = True
        job_history = []
        for ls_idx, (idx, job_title) in enumerate(idx_job_title): 
            job_info = {}
            job_info["Job Title"] = job_title.strip(" ,.;:-") if job_title else ""
            # company 
            if current_and_below: line1, line2 = idx, idx+1
            else: line1, line2 = idx, idx-1 
            job_info["Company"] = self.new_get_job_company(line1, line2, resume_segment)

            if current_and_below: st_span = idx
            else: st_span = idx-1
            # Dates 
            if ls_idx == len(idx_job_title) - 1: end_span = len(resume_segment) 
            else: end_span = idx_job_title[ls_idx+1][0]
            start, end = self.get_job_dates(st_span, end_span, resume_segment)
            job_info["Start Date"] = start
            job_info["End Date"] = end
            job_history.append(job_info)
        self.parsed_cv["Job History"] = job_history 

    def parse_job_history(self, resume_segment):
        idx_job_title = self.get_job_titles(resume_segment)
        current_and_below = False
        if not len(idx_job_title): 
            self.parsed_cv["Job History"] = [] 
            return
        if idx_job_title[0][0] == 0: current_and_below = True
        job_history = []
        for ls_idx, (idx, job_title) in enumerate(idx_job_title): 
            job_info = {}
            job_info["Job Title"] = self.filter_job_title(job_title) 
            # company 
            if current_and_below: line1, line2 = idx, idx+1
            else: line1, line2 = idx, idx-1 
            job_info["Company"] = self.get_job_company(line1, line2, resume_segment)
            if current_and_below: st_span = idx
            else: st_span = idx-1
            # Dates 
            if ls_idx == len(idx_job_title) - 1: end_span = len(resume_segment) 
            else: end_span = idx_job_title[ls_idx+1][0]
            start, end = self.get_job_dates(st_span, end_span, resume_segment)
            job_info["Start Date"] = start
            job_info["End Date"] = end
            job_history.append(job_info)
        self.parsed_cv["Job History"] = job_history 

    def get_job_titles(self, resume_segment):
        classes = ["organization", "institution", "company", "job title", "work details"]
        idx_line = []
        for idx, line in enumerate(resume_segment):
            has_verb = False
            line_modifed = ''.join(i for i in line if not i.isdigit())
            sentence = self.models.get_flair_sentence(line_modifed)
            self.tagger.predict(sentence)
            tags = []
            for entity in sentence.get_spans('pos'):
                tags.append(entity.tag)
                if entity.tag.startswith("V"): 
                    has_verb = True

            most_common_tag = max(set(tags), key=tags.count)
            if most_common_tag == "NNP":
                if not has_verb:
                    out = self.zero_shot_classifier(line, classes)
                    class_score = zip(out["labels"], out["scores"])
                    highest = sorted(class_score, key=lambda x: x[1])[-1]

                    if highest[0] == "job title":
                        idx_line.append((idx, line))

        return idx_line
    

    def get_job_dates(self, st, end, resume_segment):
        search_span = resume_segment[st:end]
        for line in search_span:
            range_match = DATE_RANGE_REGEX.search(line)
            if range_match:
                start_date = range_match.group(1).strip()
                end_date = range_match.group(2).strip()
                return self.format_date(start_date), self.format_date(end_date)
        dates = []
        for line in search_span:
            ner_entities = self.get_ner_in_line(line, "DATE")
            
            if re.search(r'\b(present|current|now|sekarang|saat\s*ini)\b', line, re.IGNORECASE):
                if not any(re.search(r'\b(present|current|now|sekarang|saat\s*ini)\b', e, re.IGNORECASE) for e in ner_entities):
                    ner_entities.append("Present")
                    
            for dt in ner_entities:
                if self.isvalidyear(dt.strip()):
                    dates.append(dt)
        if not dates:
            return ("", "")
            
        first = dates[0]
        exists_second = len(dates) > 1
        second = dates[1] if exists_second else ""
        
        if self.has_two_dates(first):
            d1, d2 = self.get_two_dates(first)
            return self.format_date(d1), self.format_date(d2)
        elif exists_second and self.has_two_dates(second): 
            d1, d2 = self.get_two_dates(second)
            return self.format_date(d1), self.format_date(d2)
        else: 
            if exists_second: 
                return self.format_date(first), self.format_date(second)
            else: 
                return self.format_date(first), ""

    
    
    def filter_job_title(self, job_title):
        job_title_splitter = re.compile(r'[{}]+'.format(re.escape(punctuation.replace("&", "") )))
        job_title = ''.join(i for i in job_title if not i.isdigit())
        tokens = job_title_splitter.split(job_title)
        tokens = [''.join([i for i in tok.strip() if (i.isalpha() or i.strip()=="")]) for tok in tokens if tok.strip()] 
        classes = ["company", "organization", "institution", "job title", "responsibility",  "details"]
        new_title = []
        for token in tokens:
            if not token: continue
            res = self.zero_shot_classifier(token, classes)
            class_score = zip(res["labels"], res["scores"])
            highest = sorted(class_score, key=lambda x: x[1])[-1]
            if highest[0] == "job title":
                new_title.append(token.strip())
        if len(new_title):
            return ', '.join(new_title)
        else: return ', '.join(tokens)

    def has_two_dates(self, date):
        date_str = str(date).lower()
        normalized_date = re.sub(r'[\–\—]', '-', date_str)
        if "-" in normalized_date or " to " in normalized_date or " sampai " in normalized_date or " hingga" in normalized_date:
            return True
        if re.search(r'\b(present|current|now|sekarang|saat\s*ini)\b', normalized_date) and re.search(r'\d{2,4}', normalized_date):
            return True
        years = re.findall(r'\b(19|20)\d{2}\b', normalized_date)
        return len(years) >= 2
    
    def get_two_dates(self, date):
        date_str = str(date)
        date_lower = date_str.lower()
        
        # Normalize dashes
        normalized_date = re.sub(r'[\–\—]', '-', date_str)
        
        # 1. Split on explicit delimiters first
        if "-" in normalized_date:
            parts = normalized_date.split("-", 1)
            return parts[0].strip(), parts[1].strip()
        elif " to " in date_lower:
            parts = re.split(r'(?i)\s+to\s+', date_str, 1)
            return parts[0].strip(), parts[1].strip()
            
        # 2. Fallback to year splitting if no explicit delimiter is present
        years = self.get_valid_years()
        idxs = []
        for year in years:
            if year in date_str:
                idxs.append(date_str.index(year))
                
        if idxs:
            min_idx = min(idxs)
            first = date_str[:min_idx+4]
            # FIXED: Removed the extra colon so it correctly slices the second half of the string
            second = date_str[min_idx+4:]
            
            # Clean up leading spaces or trailing "to" artifacts
            second = re.sub(r'^[\s\-to]+', '', second, flags=re.IGNORECASE)
            return first.strip(), second.strip()
            
        return date_str, ""

    def get_valid_years(self):
        current_year = datetime.today().year
        return [str(i) for i in range(current_year-100, current_year + 10)]

    def format_date(self, date):
        cleaned = self.clean_date(date)
        parsed = self.parse_date(cleaned)
        return parsed if parsed else cleaned

    def clean_date(self, date): 
        date_str = str(date)
        if re.search(r'\b(present|current|now|sekarang|saat\s*ini)\b', date_str, re.IGNORECASE):
            return "Present"
        cleaned = ''.join(i for i in date_str if i.isalnum() or i in ['-', '/', ' ', "'"])
        return cleaned.strip()

    def parse_date(self, date):
        if not date: return ""
        date_str = str(date).lower()
        if "present" in date_str or "current" in date_str or "now" in date_str:
            return "Present"
        month_dict = {
            "january": "01", "januari": "01", "jan": "01", 
            "february": "02", "februari": "02", "feb": "02",
            "march": "03", "maret": "03", "mar": "03", 
            "april": "04", "apr": "04",
            "may": "05", "mei": "05", 
            "june": "06", "juni": "06", "jun": "06", 
            "july": "07", "juli": "07", "jul": "07",
            "august": "08", "agustus": "08", "aug": "08", "agu": "08", 
            "september": "09", "sep": "09", "sept": "09",
            "october": "10", "oktober": "10", "oct": "10", "okt": "10", 
            "november": "11", "nov": "11",
            "december": "12", "desember": "12", "dec": "12", "des": "12"
        }
        date_clean = date.replace("'", "")
        words = re.split(r'[\s\-\/\\]+', date_clean.lower())
        month_val = ""
        year_val = ""
        for w in words:
            if w in month_dict and not month_val:
                month_val = month_dict[w]
            elif w.isdigit():
                if len(w) == 4:
                    year_val = w
                elif len(w) == 2 and not year_val:
                    year_val = "20" + w
        if month_val and year_val:
            return f"{month_val}-{year_val}"
        try:
            parsed_d = parser.parse(date_clean, default=datetime(2022, 1, 1))
            return parsed_d.strftime("%m-%Y")
        except: 
            pass
        if year_val:
            return year_val
        return date

    def isvalidyear(self, date):
        date_str = str(date).lower()
        if "present" in date_str or "current" in date_str or "now" in date_str:
            return True
        if re.search(r'\b(19|20)\d{2}\b', date_str) or re.search(r'\'\d{2}\b', date_str):
            return True
            
        return False

    def get_ner_in_line(self, line, entity_type):
        if entity_type == "DATE": ner = self.ner_dates
        else: ner = self.ner
        return [i['word'] for i in ner(line) if i['entity_group'] == entity_type]
        

    def get_job_company(self, idx, idx1, resume_segment):
        job_title = resume_segment[idx]
        if not idx1 <= len(resume_segment)-1: context = ""
        else:context = resume_segment[idx1]
        candidate_companies = self.get_ner_in_line(job_title, "ORG") + self.get_ner_in_line(context, "ORG")
        classes = ["organization", "company", "institution", "not organization", "not company", "not institution"]
        scores = []
        for comp in candidate_companies:
            res = self.zero_shot_classifier(comp, classes)['scores']
            scores.append(max(res[:3]))
        sorted_cmps = sorted(zip(candidate_companies, scores), key=lambda x: x[1], reverse=True)
        if len(sorted_cmps): return sorted_cmps[0][0]
        return context
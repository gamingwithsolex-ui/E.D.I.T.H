import re

def auto_remember(text, memory, reply=""):
    """Enhanced learning — extracts facts, profile info, preferences, and corrections."""
    low = text.lower()

    # Name detection
    name_patterns = [
        r"my name is (\w+)", r"i'm (\w+)", r"i am (\w+)",
        r"call me (\w+)", r"they call me (\w+)",
    ]
    for pat in name_patterns:
        m = re.search(pat, low)
        if m:
            name = m.group(1).capitalize()
            if name.lower() not in {"a", "the", "not", "an", "so", "very", "just", "really", "doing", "going", "looking", "trying", "using", "running", "working", "studying", "from", "good", "fine", "okay", "great", "tired", "bored", "happy", "sad", "busy", "free", "here", "there"}:
                memory.update_profile("name", name)
                break

    # Occupation detection
    occ_patterns = [
        r"i (?:work as|am) (?:a |an )?(developer|engineer|designer|student|teacher|doctor|programmer|artist|writer|manager|analyst|scientist|researcher|freelancer|consultant|architect|chef|nurse|lawyer|accountant|musician|photographer|marketer|data scientist|devops|sysadmin|admin|intern|ceo|cto|founder|entrepreneur)(?:\b)",
        r"i'm (?:a |an )?(developer|engineer|designer|student|teacher|doctor|programmer|artist|writer|manager|analyst|scientist|researcher|freelancer|consultant|architect|intern|entrepreneur)(?:\b)",
        r"i (?:study|am studying) (.+?)(?:\.|$|,)",
    ]
    for pat in occ_patterns:
        m = re.search(pat, low)
        if m:
            memory.update_profile("occupation", m.group(1).strip().capitalize())
            break

    # Location
    loc_patterns = [
        r"i (?:live in|am from|'m from|am in|stay in) (.+?)(?:\.|$|,|!)",
        r"i'm (?:in|at|from) (.+?)(?:\.|$|,|!)",
    ]
    for pat in loc_patterns:
        m = re.search(pat, low)
        if m:
            loc = m.group(1).strip().title()
            if 2 < len(loc) < 40:
                memory.update_profile("location", loc)
                break

    # Preferences
    like_patterns = [
        (r"i (?:like|love|enjoy|adore|prefer) (.+?)(?:\.|$|,|!)", "positive"),
        (r"i (?:hate|dislike|can't stand|don't like|detest) (.+?)(?:\.|$|,|!)", "negative"),
        (r"(?:my fav(?:ou?rite)?) (?:is |are )?(.+?)(?:\.|$|,|!)", "positive"),
    ]
    for pat, sentiment in like_patterns:
        m = re.search(pat, low)
        if m:
            topic = m.group(1).strip()
            if 3 < len(topic) < 50:
                memory.add_preference(topic, sentiment)
                if sentiment == "positive":
                    memory.update_profile("interests", topic)

    # Skills
    skill_patterns = [
        r"i (?:know|use|code in|program in|work with|develop with|build with) (.+?)(?:\.|$|,|!)",
        r"i'm (?:good at|skilled in|experienced with|proficient in|learning) (.+?)(?:\.|$|,|!)",
    ]
    for pat in skill_patterns:
        m = re.search(pat, low)
        if m:
            skill = m.group(1).strip().capitalize()
            if 2 < len(skill) < 40:
                memory.update_profile("skills", skill)

    # Corrections
    correction_patterns = [
        r"(?:no|nope|wrong|incorrect|actually|not right),?\s+(.+)",
        r"that's (?:wrong|not right|incorrect|not what i)",
        r"i (?:said|meant|asked) (.+)",
        r"you(?:'re| are) wrong",
    ]
    for pat in correction_patterns:
        m = re.search(pat, low)
        if m:
            correction = m.group(1).strip() if m.lastindex else text.strip()
            if len(correction) > 5:
                memory.add_correction(correction.capitalize())
            break

    # General facts
    fact_triggers = [
        "my name is", "i am", "i'm", "i like", "i hate", "i love",
        "i study", "i work", "i live", "my favourite", "my favorite",
        "i have", "i use", "i play", "i'm from", "call me",
        "i need", "i want", "i prefer", "i own", "i drive",
        "i speak", "i know", "my hobby", "my hobbies", "my goal",
        "my age", "i'm learning", "my birthday", "my email", "my phone",
        "i go to", "i attend", "my school", "my university", "my college",
        "my pet", "my dog", "my cat", "my car", "my setup",
    ]
    for t in fact_triggers:
        if t in low:
            for sentence in re.split(r"[.!?]", text):
                if t in sentence.lower() and len(sentence.strip()) > 5:
                    memory.add_fact(sentence.strip().capitalize())
            break

    # Adaptive Interaction Style
    style_updated = False
    
    # Detail preference
    if any(w in low for w in ["explain in detail", "tell me more", "elaborate", "go deeper", "more detail"]):
        memory.data["interaction_style"]["prefers_detail"] = True
        style_updated = True
    elif any(w in low for w in ["keep it short", "brief", "tldr", "summarize", "shorter", "stop talking", "too long"]):
        memory.data["interaction_style"]["prefers_detail"] = False
        style_updated = True
        
    # Humor preference
    if any(w in low for w in ["haha", "lol", "lmao", "funny", "good one", "joke", "make me laugh"]):
        memory.data["interaction_style"]["prefers_humor"] = True
        style_updated = True
    elif any(w in low for w in ["not funny", "stop joking", "be serious", "this is serious"]):
        memory.data["interaction_style"]["prefers_humor"] = False
        style_updated = True
        
    # Formality preference
    if any(w in low for w in ["be professional", "formal", "proper"]):
        memory.data["interaction_style"]["formality"] = "professional"
        style_updated = True
    elif any(w in low for w in ["chill", "casual", "relax", "dude", "bro", "mate"]):
        memory.data["interaction_style"]["formality"] = "casual"
        style_updated = True
        
    # Tone preference
    if any(w in low for w in ["comfort me", "i'm sad", "i'm depressed", "feeling down"]):
        memory.data["interaction_style"]["tone"] = "extra warm and empathetic"
        style_updated = True

    if style_updated:
        memory.save()

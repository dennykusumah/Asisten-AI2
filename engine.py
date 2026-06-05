"""
engine.py — Keyword extraction engine (no AI/API)
Methods: TF-IDF, RAKE, and frequency-based analysis
"""

import re
import math
from collections import Counter, defaultdict
from typing import List, Dict, Tuple


# ─── Stopwords (Indonesian + English) ──────────────────────────────────────────

STOPWORDS_EN = {
    "a","about","above","after","again","against","all","am","an","and","any",
    "are","aren't","as","at","be","because","been","before","being","below",
    "between","both","but","by","can","can't","cannot","could","couldn't","did",
    "didn't","do","does","doesn't","doing","don't","down","during","each","few",
    "for","from","further","get","got","had","hadn't","has","hasn't","have",
    "haven't","having","he","he'd","he'll","he's","her","here","here's","hers",
    "herself","him","himself","his","how","how's","i","i'd","i'll","i'm","i've",
    "if","in","into","is","isn't","it","it's","its","itself","let's","me","more",
    "most","mustn't","my","myself","no","nor","not","of","off","on","once",
    "only","or","other","ought","our","ours","ourselves","out","over","own",
    "same","shan't","she","she'd","she'll","she's","should","shouldn't","so",
    "some","such","than","that","that's","the","their","theirs","them",
    "themselves","then","there","there's","these","they","they'd","they'll",
    "they're","they've","this","those","through","to","too","under","until",
    "up","very","was","wasn't","we","we'd","we'll","we're","we've","were",
    "weren't","what","what's","when","when's","where","where's","which","while",
    "who","who's","whom","why","why's","will","with","won't","would","wouldn't",
    "you","you'd","you'll","you're","you've","your","yours","yourself","yourselves",
    "also","may","much","many","well","one","two","three","four","five","six",
    "seven","eight","nine","ten","however","therefore","thus","hence","since",
    "use","used","using","used","based","given","provide","provides","provided",
    "include","includes","including","within","without","whether","via","per",
    "etc","i.e","e.g","new","old","large","small","high","low","good","bad",
    "first","second","last","next","like","just","even","still","already",
    "always","never","often","sometimes","usually","generally","specifically",
    "particularly","especially","rather","quite","very","really","simply",
    "certain","various","different","several","another","every","each","both",
    "either","neither","nor","yet","though","although","despite","whereas",
    "while","meanwhile","otherwise","moreover","furthermore","additionally",
    "consequently","subsequently","finally","initially","previously","currently",
    "recently","according","related","regarding","among","upon","along",
    "across","around","throughout","toward","towards","away","back","forward",
    "together","apart","instead","rather","enough","here","there","where",
    "when","how","why","which","who","whom","whose","what","that","this",
    "these","those","make","made","making","take","takes","taking","taken",
    "come","comes","coming","came","go","goes","going","went","gone","see",
    "sees","seeing","saw","seen","know","knows","knowing","knew","known",
    "think","thinks","thinking","thought","want","wants","wanting","wanted",
    "look","looks","looking","looked","need","needs","needing","needed",
    "show","shows","showing","showed","shown","find","finds","finding","found",
    "give","gives","giving","gave","given","tell","tells","telling","told",
    "seem","seems","seeming","seemed","say","says","saying","said","put",
    "puts","putting","call","calls","calling","called","ask","asks","asking",
    "asked","turn","turns","turning","turned","keep","keeps","keeping","kept",
    "help","helps","helping","helped","set","sets","setting","run","runs",
    "running","ran","hold","holds","holding","held","move","moves","moving",
    "moved","work","works","working","worked","play","plays","playing","played",
    "let","lets","letting","begin","begins","beginning","began","begun",
    "seem","try","tries","trying","tried","leave","leaves","leaving","left",
    "might","could","should","would","shall","will","may","can","must",
    "number","numbers","way","ways","time","times","day","days","year","years",
    "part","parts","place","places","case","cases","point","points","fact",
    "facts","example","examples","type","types","kind","kinds","form","forms",
    "level","levels","line","lines","group","groups","area","areas","end","ends",
    "hand","hands","side","sides","head","heads","page","pages","name","names",
    "home","homes","house","houses","world","words","word","right","rights",
    "long","short","little","own","same","different","few","many","most","much",
    "other","others","another","such","any","some","no","all","both","each",
    "more","less","just","only","even","still","now","than","then","so","as",
    "if","or","and","but","because","by","at","on","in","of","to","for",
    "with","is","was","are","were","be","been","being","have","has","had",
    "do","does","did","will","would","could","should","may","might","must",
    "shall","can","need","dare","ought","used","do","did","does",
}

STOPWORDS_ID = {
    "yang","dan","di","ini","itu","dengan","untuk","dari","dalam","pada",
    "ke","adalah","ada","akan","juga","tidak","atau","oleh","sudah","telah",
    "dapat","bisa","lebih","serta","sebagai","harus","saat","sangat","agar",
    "namun","tapi","tetapi","karena","ketika","setelah","sebelum","sedang",
    "semua","berbagai","bagi","tersebut","antara","tentang","bahwa","seperti",
    "secara","antara","selain","setiap","melalui","masih","terhadap","lain",
    "hal","cara","tahun","saya","kami","kita","mereka","dia","ia","nya",
    "nya","anda","kamu","mereka","kami","kita","beliau","aku","mu","ku",
    "pun","pula","lagi","mana","bukan","jika","apabila","sehingga","maka",
    "hingga","hanya","begitu","sudah","telah","sedang","sedangkan","kemudian",
    "selama","selanjutnya","yaitu","yakni","antara","baik","besar","kecil",
    "lain","lainnya","sama","saling","sesama","setiap","masing","diri",
    "sendiri","beberapa","banyak","sedikit","cukup","sangat","amat","terlalu",
    "sebuah","suatu","sebuah","sebuah","suatu","tersebut","dimana","ketika",
    "meski","walaupun","meskipun","kendati","biarpun","padahal","justru",
    "bahkan","apalagi","terlebih","terutama","khususnya","umumnya","biasanya",
    "akhirnya","pertama","kedua","ketiga","selain","sehingga","oleh","karena",
    "sebab","akibat","dampak","pengaruh","peran","fungsi","tujuan","manfaat",
    "hasil","proses","langkah","tahapan","metode","sistem","bentuk","jenis",
    "macam","contoh","misalnya","seperti","antara","lain","yaitu","yakni",
    "terkait","berkaitan","berhubungan","mengenai","perihal","soal","masalah",
    "ada","adanya","adakah","terdapat","berupa","merupakan","adalah","ialah",
    "yakni","yaitu","artinya","maksudnya","dalam","pada","di","ke","dari",
    "dan","atau","tetapi","namun","juga","pun","bahkan","malah","justru",
    "per","via","bagi","oleh","untuk","atas","bawah","depan","belakang",
    "kiri","kanan","atas","bawah","sini","sana","situ","mana","mana",
    "nya","ku","mu","kah","lah","pun","tah","deh","dong","nih","sih","lho",
    "loh","oh","ah","eh","ih","uh","hem","hm","wah","nah","ya","iya","yuk",
}

STOPWORDS = STOPWORDS_EN | STOPWORDS_ID


# ─── Text Utilities ─────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Normalize text: lowercase, remove special chars, collapse whitespace."""
    text = text.lower()
    text = re.sub(r'[^\w\s\-]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def tokenize(text: str) -> List[str]:
    """Tokenize and filter: min 3 chars, not stopword, not purely numeric."""
    tokens = re.findall(r'\b[a-zA-Z][a-zA-Z\-]{2,}\b', text.lower())
    return [t for t in tokens if t not in STOPWORDS and not t.isdigit()]


def split_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def split_into_chunks(text: str, chunk_size: int = 500) -> List[str]:
    """Split text into word-level chunks (for TF-IDF 'document' simulation)."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk = ' '.join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks if chunks else [text]


# ─── Method 1: TF-IDF ──────────────────────────────────────────────────────────

def compute_tfidf(text: str, top_n: int = 30) -> List[Tuple[str, float]]:
    """
    Simulate TF-IDF by treating the document as a set of chunks.
    Keywords with high term frequency but low document frequency rank highest.
    """
    chunks = split_into_chunks(text, chunk_size=300)
    num_chunks = len(chunks)

    # Term frequency per chunk
    chunk_tokens = [tokenize(clean_text(c)) for c in chunks]
    df = Counter()  # document frequency
    for tokens in chunk_tokens:
        for t in set(tokens):
            df[t] += 1

    # Aggregate TF across whole document
    all_tokens = tokenize(clean_text(text))
    tf = Counter(all_tokens)
    total = sum(tf.values()) or 1

    scores = {}
    for term, count in tf.items():
        tf_val = count / total
        idf_val = math.log((num_chunks + 1) / (df.get(term, 0) + 1)) + 1
        scores[term] = round(tf_val * idf_val, 6)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]


# ─── Method 2: RAKE (Rapid Automatic Keyword Extraction) ───────────────────────

def compute_rake(text: str, top_n: int = 30) -> List[Tuple[str, float]]:
    """
    RAKE: extract candidate phrases (split by stopwords/punctuation),
    score each word by degree/frequency, score phrase as sum of word scores.
    """
    # Build candidate phrases
    phrase_pattern = re.compile(
        r'(?:[^' + re.escape(''.join(['.', ',', ';', ':', '!', '?', '(', ')', '\n', '\t', '"', "'"])) + r']+)'
    )
    clean = clean_text(text)
    # Split on stopwords and punctuation
    stop_pat = r'\b(' + '|'.join(re.escape(w) for w in sorted(STOPWORDS, key=len, reverse=True)) + r')\b'
    segments = re.split(stop_pat + r'|[,;:\.\!\?\(\)\"\'\n]', clean)

    candidates = []
    for seg in segments:
        seg = seg.strip() if seg else ''
        words = [w for w in seg.split() if len(w) >= 3 and re.match(r'^[a-zA-Z\-]+$', w)]
        if 1 <= len(words) <= 5:
            candidates.append(words)

    # Word score = degree / frequency
    word_freq: Dict[str, int] = defaultdict(int)
    word_degree: Dict[str, int] = defaultdict(int)
    for phrase in candidates:
        for w in phrase:
            word_freq[w] += 1
            word_degree[w] += len(phrase) - 1

    word_score = {w: (word_degree[w] + word_freq[w]) / word_freq[w]
                  for w in word_freq}

    # Phrase scores
    phrase_scores: Dict[str, float] = {}
    for phrase in candidates:
        phrase_str = ' '.join(phrase)
        score = sum(word_score.get(w, 0) for w in phrase)
        if phrase_str not in phrase_scores or score > phrase_scores[phrase_str]:
            phrase_scores[phrase_str] = round(score, 4)

    return sorted(phrase_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]


# ─── Method 3: Frequency + Bigrams ─────────────────────────────────────────────

def compute_frequency(text: str, top_n: int = 30) -> List[Tuple[str, float]]:
    """
    Combine unigram frequency + bigram frequency to capture multi-word keywords.
    Score normalized to [0, 1].
    """
    tokens = tokenize(clean_text(text))
    unigram = Counter(tokens)

    bigrams = [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)
               if tokens[i] not in STOPWORDS and tokens[i+1] not in STOPWORDS]
    bigram_c = Counter(bigrams)

    # Merge: bigrams weighted x2
    combined: Dict[str, float] = {}
    for w, c in unigram.items():
        combined[w] = float(c)
    for bg, c in bigram_c.items():
        if c >= 2:  # only meaningful bigrams
            combined[bg] = float(c) * 1.8

    max_score = max(combined.values(), default=1)
    normalized = {k: round(v / max_score, 4) for k, v in combined.items()}

    return sorted(normalized.items(), key=lambda x: x[1], reverse=True)[:top_n]


# ─── Combined Ensemble ─────────────────────────────────────────────────────────

def extract_keywords(
    text: str,
    method: str = "ensemble",
    top_n: int = 30,
    min_score: float = 0.0,
) -> List[Dict]:
    """
    Main extraction function.

    Parameters
    ----------
    text    : raw PDF text
    method  : 'tfidf' | 'rake' | 'frequency' | 'ensemble'
    top_n   : number of keywords to return
    min_score: minimum normalized score threshold

    Returns
    -------
    List of dicts with keys: keyword, score, method
    """
    if not text or len(text.strip()) < 50:
        return []

    results: List[Tuple[str, float]] = []

    if method in ("tfidf", "ensemble"):
        results += [(kw, sc, "TF-IDF") for kw, sc in compute_tfidf(text, top_n)]

    if method in ("rake", "ensemble"):
        results += [(kw, sc, "RAKE") for kw, sc in compute_rake(text, top_n)]

    if method in ("frequency", "ensemble"):
        results += [(kw, sc, "Frequency") for kw, sc in compute_frequency(text, top_n)]

    if method == "ensemble":
        # Normalize each method's scores to [0,1] and average across methods
        from collections import defaultdict
        kw_scores: Dict[str, List[float]] = defaultdict(list)
        kw_method: Dict[str, List[str]] = defaultdict(list)

        # Group by method and normalize within each
        method_groups: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        for kw, sc, m in results:
            method_groups[m].append((kw, sc))

        for m, pairs in method_groups.items():
            max_sc = max(s for _, s in pairs) if pairs else 1
            for kw, sc in pairs:
                norm = sc / max_sc if max_sc else 0
                kw_scores[kw].append(norm)
                kw_method[kw].append(m)

        combined = [
            {
                "keyword": kw,
                "score": round(sum(scores) / len(scores), 4),
                "method": " + ".join(sorted(set(kw_method[kw]))),
            }
            for kw, scores in kw_scores.items()
        ]
        combined = [r for r in combined if r["score"] >= min_score]
        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined[:top_n]

    # Single method
    seen = set()
    final = []
    for kw, sc, m in results:
        if kw not in seen and sc >= min_score:
            seen.add(kw)
            final.append({"keyword": kw, "score": round(sc, 4), "method": m})

    final.sort(key=lambda x: x["score"], reverse=True)
    return final[:top_n]


# ─── Document Stats ─────────────────────────────────────────────────────────────

def document_stats(text: str) -> Dict:
    """Return basic document statistics."""
    words = text.split()
    sentences = split_sentences(text)
    tokens = tokenize(clean_text(text))
    return {
        "total_chars": len(text),
        "total_words": len(words),
        "total_sentences": len(sentences),
        "unique_tokens": len(set(tokens)),
        "avg_sentence_length": round(len(words) / max(len(sentences), 1), 1),
    }

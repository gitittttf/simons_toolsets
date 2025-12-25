"""
Content Scorer - Bewertet QR-Code-Inhalte basierend auf Wörterbuch und URL-Patterns

Dieses Modul analysiert dekodierten QR-Code-Text und berechnet einen Confidence-Score
basierend auf:
- URL-Muster (https://, www., etc.)
- Wörterbuch-Matches (Englisch + Deutsch)
- Text-Lesbarkeit
"""

import re
import os
from dataclasses import dataclass
from typing import List, Set, Tuple, Optional
from pathlib import Path


@dataclass
class ContentScore:
    """Detailliertes Scoring-Ergebnis für QR-Inhalt"""
    total_score: float          # Gesamt-Score (0.0 - 1.0)
    
    # URL-Analyse
    is_url: bool
    url_score: float            # 0.0 - 1.0
    url_type: Optional[str]     # "https", "http", "www", None
    
    # Wörterbuch-Analyse
    dictionary_score: float     # 0.0 - 1.0
    german_matches: List[str]
    english_matches: List[str]
    word_count: int
    
    # Lesbarkeit
    readability_score: float    # 0.0 - 1.0
    printable_ratio: float      # Anteil druckbarer Zeichen
    
    # Debug-Info
    debug_info: str = ""
    
    def __repr__(self):
        return (f"ContentScore(total={self.total_score:.2%}, "
                f"url={self.url_score:.2%}, dict={self.dictionary_score:.2%}, "
                f"read={self.readability_score:.2%})")


class ContentScorer:
    """
    Bewertet QR-Code-Inhalte auf Plausibilität
    
    Scoring-Gewichte:
    - URL-Erkennung: 40%
    - Wörterbuch-Matches: 40%
    - Lesbarkeit: 20%
    """
    
    # URL-Patterns mit Scores
    URL_PATTERNS = [
        (r'^https://', 'https', 0.5),
        (r'^http://', 'http', 0.4),
        (r'^www\.', 'www', 0.3),
        (r'\.com(/|$)', 'tld_com', 0.2),
        (r'\.de(/|$)', 'tld_de', 0.2),
        (r'\.org(/|$)', 'tld_org', 0.2),
        (r'\.net(/|$)', 'tld_net', 0.2),
        (r'\.io(/|$)', 'tld_io', 0.15),
        (r'\.info(/|$)', 'tld_info', 0.15),
        (r'@[\w.-]+\.\w+', 'email', 0.4),  # E-Mail Pattern
    ]
    
    # Vollständige URL-Regex
    FULL_URL_REGEX = re.compile(
        r'^https?://[a-zA-Z0-9][-a-zA-Z0-9]*(\.[a-zA-Z0-9][-a-zA-Z0-9]*)+(/[-a-zA-Z0-9._~:/?#\[\]@!$&\'()*+,;=%]*)?$'
    )
    
    # Gewichte für Gesamtscore
    WEIGHT_URL = 0.40
    WEIGHT_DICTIONARY = 0.40
    WEIGHT_READABILITY = 0.20
    
    def __init__(self, dictionaries_path: Optional[str] = None):
        """
        Initialisiert den ContentScorer
        
        Args:
            dictionaries_path: Pfad zum Wörterbuch-Ordner (optional)
        """
        self.german_words: Set[str] = set()
        self.english_words: Set[str] = set()
        
        # Bestimme Wörterbuch-Pfad
        if dictionaries_path:
            dict_path = Path(dictionaries_path)
        else:
            # Standard: dictionaries Ordner neben diesem Modul
            dict_path = Path(__file__).parent.parent / "dictionaries"
        
        self._load_dictionaries(dict_path)
        
        # Kompiliere URL-Patterns
        self.compiled_url_patterns = [
            (re.compile(pattern, re.IGNORECASE), name, score)
            for pattern, name, score in self.URL_PATTERNS
        ]
    
    def _load_dictionaries(self, dict_path: Path):
        """Lädt Wörterbücher aus Dateien"""
        german_file = dict_path / "german_words.txt"
        english_file = dict_path / "english_words.txt"
        
        # Lade deutsches Wörterbuch
        if german_file.exists():
            try:
                with open(german_file, 'r', encoding='utf-8') as f:
                    self.german_words = {
                        line.strip().lower() 
                        for line in f 
                        if line.strip() and len(line.strip()) >= 3
                    }
                print(f"✓ Deutsches Wörterbuch geladen: {len(self.german_words):,} Wörter")
            except Exception as e:
                print(f"⚠️ Fehler beim Laden des deutschen Wörterbuchs: {e}")
        else:
            print(f"⚠️ Deutsches Wörterbuch nicht gefunden: {german_file}")
            # Fallback: Einige häufige deutsche Wörter
            self.german_words = self._get_fallback_german_words()
        
        # Lade englisches Wörterbuch
        if english_file.exists():
            try:
                with open(english_file, 'r', encoding='utf-8') as f:
                    self.english_words = {
                        line.strip().lower() 
                        for line in f 
                        if line.strip() and len(line.strip()) >= 3
                    }
                print(f"✓ Englisches Wörterbuch geladen: {len(self.english_words):,} Wörter")
            except Exception as e:
                print(f"⚠️ Fehler beim Laden des englischen Wörterbuchs: {e}")
        else:
            print(f"⚠️ Englisches Wörterbuch nicht gefunden: {english_file}")
            # Fallback: Einige häufige englische Wörter
            self.english_words = self._get_fallback_english_words()
    
    def _get_fallback_german_words(self) -> Set[str]:
        """Fallback: Häufige deutsche Wörter"""
        return {
            'der', 'die', 'das', 'und', 'ist', 'von', 'sie', 'den', 'nicht',
            'mit', 'ein', 'eine', 'auf', 'dem', 'sich', 'des', 'auch', 'für',
            'als', 'werden', 'aus', 'hat', 'haben', 'sind', 'wird', 'bei',
            'noch', 'nach', 'nur', 'war', 'oder', 'aber', 'vor', 'wenn',
            'mehr', 'durch', 'über', 'dann', 'können', 'schon', 'hier',
            'ohne', 'unter', 'gibt', 'weil', 'kann', 'diese', 'dieser',
            'hallo', 'welt', 'test', 'link', 'seite', 'text', 'bild',
            'name', 'mail', 'kontakt', 'info', 'startseite', 'willkommen',
        }
    
    def _get_fallback_english_words(self) -> Set[str]:
        """Fallback: Häufige englische Wörter"""
        return {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can',
            'had', 'her', 'was', 'one', 'our', 'out', 'has', 'his', 'how',
            'man', 'new', 'now', 'old', 'see', 'way', 'who', 'boy', 'did',
            'its', 'let', 'say', 'she', 'too', 'use', 'been', 'call', 'come',
            'could', 'down', 'find', 'first', 'from', 'get', 'have', 'here',
            'into', 'just', 'know', 'like', 'long', 'look', 'make', 'more',
            'hello', 'world', 'test', 'link', 'page', 'text', 'image',
            'name', 'mail', 'contact', 'info', 'home', 'welcome', 'website',
            'click', 'here', 'read', 'more', 'search', 'about', 'help',
        }
    
    def score_content(self, text: Optional[str]) -> ContentScore:
        """
        Berechnet Gesamtscore für dekodierten QR-Text
        
        Args:
            text: Dekodierter QR-Code-Text (kann None sein)
            
        Returns:
            ContentScore mit detaillierten Scoring-Informationen
        """
        if not text:
            return ContentScore(
                total_score=0.0,
                is_url=False,
                url_score=0.0,
                url_type=None,
                dictionary_score=0.0,
                german_matches=[],
                english_matches=[],
                word_count=0,
                readability_score=0.0,
                printable_ratio=0.0,
                debug_info="Kein Text zum Analysieren"
            )
        
        debug_parts = []
        
        # 1. URL-Analyse
        url_score, url_type, is_url = self._analyze_url(text)
        debug_parts.append(f"URL: {url_score:.2%} ({url_type or 'keine'})")
        
        # 2. Wörterbuch-Analyse
        dict_score, german_matches, english_matches = self._analyze_dictionary(text)
        word_count = len(german_matches) + len(english_matches)
        debug_parts.append(f"Dict: {dict_score:.2%} ({word_count} Wörter)")
        
        # 3. Lesbarkeit
        read_score, printable_ratio = self._analyze_readability(text)
        debug_parts.append(f"Read: {read_score:.2%}")
        
        # Gesamt-Score berechnen
        # Bei URLs gewichten wir anders
        if is_url:
            # URLs bekommen Bonus
            total_score = (
                url_score * 0.50 +
                dict_score * 0.30 +
                read_score * 0.20
            )
        else:
            # Normale Texte
            total_score = (
                url_score * self.WEIGHT_URL +
                dict_score * self.WEIGHT_DICTIONARY +
                read_score * self.WEIGHT_READABILITY
            )
        
        # Boost für vollständige URLs
        if self.FULL_URL_REGEX.match(text):
            total_score = min(1.0, total_score + 0.2)
            debug_parts.append("(Vollständige URL)")
        
        return ContentScore(
            total_score=min(1.0, total_score),
            is_url=is_url,
            url_score=url_score,
            url_type=url_type,
            dictionary_score=dict_score,
            german_matches=german_matches,
            english_matches=english_matches,
            word_count=word_count,
            readability_score=read_score,
            printable_ratio=printable_ratio,
            debug_info=" | ".join(debug_parts)
        )
    
    def _analyze_url(self, text: str) -> Tuple[float, Optional[str], bool]:
        """
        Analysiert URL-Patterns im Text
        
        Returns:
            (score, url_type, is_url)
        """
        score = 0.0
        url_type = None
        is_url = False
        
        for pattern, ptype, pscore in self.compiled_url_patterns:
            if pattern.search(text):
                score += pscore
                if url_type is None:
                    url_type = ptype
                is_url = True
        
        # Cap bei 1.0
        return min(score, 1.0), url_type, is_url
    
    def _analyze_dictionary(self, text: str) -> Tuple[float, List[str], List[str]]:
        """
        Analysiert Wörterbuch-Matches im Text
        
        Returns:
            (score, german_matches, english_matches)
        """
        # Extrahiere Wörter (nur Buchstaben, min. 3 Zeichen)
        words = re.findall(r'[a-zA-ZäöüÄÖÜß]{3,}', text.lower())
        
        german_matches = []
        english_matches = []
        
        for word in words:
            if word in self.german_words:
                german_matches.append(word)
            elif word in self.english_words:
                english_matches.append(word)
        
        total_words = len(words)
        matched_words = len(german_matches) + len(english_matches)
        
        if total_words == 0:
            return 0.0, german_matches, english_matches
        
        # Score basierend auf Match-Rate
        match_ratio = matched_words / total_words
        
        # Bonus für mehr Matches
        bonus = min(0.3, matched_words * 0.03)
        
        score = min(1.0, match_ratio * 0.7 + bonus)
        
        return score, german_matches, english_matches
    
    def _analyze_readability(self, text: str) -> Tuple[float, float]:
        """
        Analysiert Lesbarkeit des Textes
        
        Returns:
            (score, printable_ratio)
        """
        if not text:
            return 0.0, 0.0
        
        # Zähle druckbare ASCII-Zeichen
        printable = sum(1 for c in text if 32 <= ord(c) < 127 or c in 'äöüÄÖÜß\n\r\t')
        total = len(text)
        
        printable_ratio = printable / total if total > 0 else 0.0
        
        # Score-Berechnung
        score = printable_ratio
        
        # Bonus für vernünftige Textlänge (5-500 Zeichen)
        if 5 <= len(text) <= 500:
            score = min(1.0, score + 0.1)
        
        # Malus für Kontrollzeichen (außer Newlines)
        control_chars = sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t')
        if control_chars > 0:
            score = max(0.0, score - 0.3)
        
        return score, printable_ratio


# Singleton-Instanz für einfachen Zugriff
_default_scorer: Optional[ContentScorer] = None


def get_content_scorer() -> ContentScorer:
    """Gibt die Standard-Scorer-Instanz zurück (Lazy-Loading)"""
    global _default_scorer
    if _default_scorer is None:
        _default_scorer = ContentScorer()
    return _default_scorer

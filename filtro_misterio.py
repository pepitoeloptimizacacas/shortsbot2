"""Preselección temática; la IA revisa después la intriga y el desenlace."""
import re

FUENTES_FICCION = {'nosleep', 'shortscarystories', 'creepypasta'}
PISTAS = (
    r'\b(?:strange|unexplained|whisper\w*|scream\w*|knock\w*|footsteps|noises?|scratching)\b',
    r'\b(?:basement|attic|abandoned|locked|hidden|secret|laborator\w*|tunnel\w*|cellar)\b',
    r'\b(?:disappear\w*|missing|stalk\w*|followed|trapped|intruder|blood|dead|corpse|body|bodies)\b',
    r'\b(?:discovered|revealed|realized|found out|behind the door|recording|footage|evidence|truth)\b',
    r'\b(?:terrifying|terrified|horror|haunted|paranormal|creature|ritual|nightmare|not human)\b',
)


def puntuar_misterio(titulo, texto):
    if re.search(r'(?i)\b(?:part|chapter|episode)\s*(?:\d+|[ivx]+)\b|\[series\]', titulo):
        return 0  # Una historia completa, no un episodio suelto.
    contenido = titulo + '\n' + texto
    return sum(bool(re.search(patron, contenido, re.I)) for patron in PISTAS)

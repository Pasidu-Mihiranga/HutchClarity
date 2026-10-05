"""How-to knowledge articles for the non-account Clarity path.

**Three languages, because the template quotes verbatim (F5).** K03 composes a
grounded answer by quoting a retrieved clause word for word, which is what
makes a citation checkable. The consequence is that a corpus in one language
answers every customer in that language: a Sinhala speaker asking a Sinhala
question got a correct answer quoting English, which is not an answer to them.

So each article exists three times, as `KB-X`, `KB-X-SI` and `KB-X-TA`, with
its own `language` and its own keywords in its own script. Retrieval prefers a
chunk in the query's language (`rerank.language_bonus`) without filtering the
others out, so a Sinhala question still reaches an English-only clause when
that is all there is, rather than being refused.

These are translations of content that was already here and already labelled
simulated. Nothing about HUTCH policy is invented by them (I16); they describe
the same app steps in another language.

**REQUIRES HUTCH CONFIRMATION**: the real corpus is CX-approved copy per
language, not a translation of an English draft, and the Sinhala and Tamil here
have not been reviewed by a native speaker.
"""

from __future__ import annotations

from typing import Any

KNOWLEDGE_ARTICLES: list[dict[str, Any]] = [
    {
        "article_id": "KB-ESIM",
        "title": "Convert or replace a SIM with an eSIM",
        "body": (
            "You can convert a physical Hutch SIM to an eSIM, or replace a lost eSIM, "
            "from the Hutch app or at a Hutch Experience Centre.\n\n"
            "1. Sign in with the number you want to convert.\n"
            "2. Open More → SIM / eSIM → Convert to eSIM (or Replace eSIM).\n"
            "3. Confirm with the OTP sent to that number.\n"
            "4. Scan the QR code on the phone that will hold the eSIM.\n"
            "5. Keep the old SIM until the new eSIM shows Active.\n\n"
            "Your number, balance and packs move with the eSIM. Packs do not restart. "
            "If conversion fails, keep using the physical SIM and visit a Hutch centre "
            "with your NIC."
        ),
        "keywords": [
            "esim",
            "e-sim",
            "convert",
            "replace",
            "sim",
            "qr",
            "how",
            "activate esim",
        ],
        "language": "en",
    },
    {
        "article_id": "KB-ACTIVATE-PACK",
        "title": "Activate a data pack",
        "body": (
            "To activate a pack on this number:\n\n"
            "1. Open Packages in the Hutch app.\n"
            "2. Choose Anytime, Unlimited, Social, Work or Combo.\n"
            "3. Confirm the price will debit your main balance.\n"
            "4. Wait for the confirmation SMS. The pack shows under Usage.\n\n"
            "If activation fails, your balance is not kept for that attempt. Try again "
            "or ask Clarity why a pack did not activate - that is an account check, "
            "not this how-to."
        ),
        "keywords": [
            "activate",
            "pack",
            "package",
            "buy",
            "purchase",
            "data",
            "how",
            "anytime",
        ],
        "language": "en",
    },
    {
        "article_id": "KB-CHECK-BALANCE",
        "title": "Check your balance",
        "body": (
            "Your main balance is on Home. Dial *#100# or open the Hutch app. "
            "Reloads from banks can take a few minutes to credit. If money left your "
            "bank but the balance did not rise, ask Clarity - that is an account "
            "investigation, not this article."
        ),
        "keywords": ["balance", "check", "reload", "credit", "how", "main balance"],
        "language": "en",
    },
    {
        "article_id": "KB-FUP",
        "title": "What fair-use (FUP) means",
        "body": (
            "Unlimited and large data packs include a fair-use cap shown at purchase. "
            "After you use that volume, speed drops to the stated rate - data is not "
            "cut off. The cap and after-cap speed are on the pack screen before you buy. "
            "If your data is slow and you want to know whether you hit the cap on this "
            "number, ask Clarity to check your account."
        ),
        "keywords": [
            "fup",
            "fair",
            "use",
            "cap",
            "slow",
            "throttle",
            "unlimited",
            "speed",
        ],
        "language": "en",
    },
    {
        "article_id": "KB-VAS",
        "title": "Manage subscriptions (VAS)",
        "body": (
            "Paid daily or monthly services (games, news, tones) appear under "
            "Subscriptions. You can cancel any active one there. Hutch must hold OTP "
            "or second-confirmation evidence for a VAS charge. If you see a charge "
            "you never confirmed, ask Clarity to check this number - that opens an "
            "account case, not this how-to alone."
        ),
        "keywords": [
            "vas",
            "subscription",
            "cancel",
            "gamehub",
            "otp",
            "manage",
            "daily",
        ],
        "language": "en",
    },
]


#: Sinhala and Tamil versions of the five articles above (F5).
#:
#: Same `article_id` stem with a language suffix, so a reader can see at a
#: glance that three rows are one article. They are separate sources rather
#: than one source with three bodies because retrieval filters and cites per
#: language, and a citation has to name the text it quoted.
KNOWLEDGE_ARTICLES += [
    {
        "article_id": 'KB-ESIM-SI',
        "title": 'SIM එකක් eSIM එකක් බවට හැරවීම හෝ ප්\u200dරතිස්ථාපනය',
        "body": (
            'Hutch භෞතික SIM එකක් eSIM එකක් බවට හැරවීම, නැතහොත් නැති වූ eSIM එකක් '
            'ප්\u200dරතිස්ථාපනය කිරීම, Hutch යෙදුමෙන් හෝ Hutch Experience Centre එකකින් කළ හැකිය.\n'
            '\n1. හැරවීමට අවශ්\u200dය අංකයෙන් ඇතුළු වන්න.\n2. තව → SIM / eSIM → eSIM බවට හරවන්න (හෝ'
            'eSIM ප්\u200dරතිස්ථාපනය) තෝරන්න.\n3. එම අංකයට එන OTP එකෙන් තහවුරු කරන්න.\n4. eSIM තබා '
            'ගන්නා දුරකථනයේ QR කේතය scan කරන්න.\n5. නව eSIM එක Active ලෙස පෙන්වන තුරු පැරණි SIM එක '
            'තබා ගන්න.\n\nඔබේ අංකය, ශේෂය සහ පැකේජ eSIM එක සමඟ මාරු වේ. පැකේජ නැවත ආරම්භ නොවේ. '
            'හැරවීම අසාර්ථක නම්, භෞතික SIM එක භාවිත කරමින් ඔබේ හැඳුනුම්පත සමඟ Hutch '
            'මධ්\u200dයස්ථානයකට යන්න.'
        ),
        "keywords": ['esim', 'ඊසිම්', 'සිම්', 'හරවන්න', 'ප්\u200dරතිස්ථාපනය', 'කොහොමද', 'qr'],
        "language": 'si',
    },
    {
        "article_id": 'KB-ACTIVATE-PACK-SI',
        "title": 'ඩේටා පැකේජයක් සක්\u200dරිය කිරීම',
        "body": (
            'මෙම අංකයේ පැකේජයක් සක්\u200dරිය කිරීමට:\n\n1. Hutch යෙදුමේ Packages විවෘත කරන්න.\n2. '
            'Anytime, Unlimited, Social, Work හෝ Combo තෝරන්න.\n3. මිල ඔබේ ප්\u200dරධාන ශේෂයෙන් අඩු'
            'වන බව තහවුරු කරන්න.\n4. තහවුරු කිරීමේ SMS එක එනතුරු රැඳී සිටින්න. පැකේජය Usage යටතේ '
            'පෙන්වයි.\n\nසක්\u200dරිය කිරීම අසාර්ථක නම්, එම උත්සාහය සඳහා ඔබේ ශේෂය රඳවා නොගනී. නැවත '
            'උත්සාහ කරන්න, නැතහොත් පැකේජයක් සක්\u200dරිය නොවූයේ මන්ද යන්න Clarity ගෙන් අසන්න - එය '
            'ගිණුම් පරීක්ෂාවකි, මෙම මාර්ගෝපදේශය නොවේ.'
        ),
        "keywords": ['පැකේජය', 'සක්\u200dරිය', 'ඩේටා', 'මිලදී', 'කොහොමද', 'activate', 'pack'],
        "language": 'si',
    },
    {
        "article_id": 'KB-CHECK-BALANCE-SI',
        "title": 'ඔබේ ශේෂය පරීක්ෂා කිරීම',
        "body": (
            'ඔබේ ප්\u200dරධාන ශේෂය Home තිරයේ ඇත. *#100# ඩයල් කරන්න, නැතහොත් Hutch යෙදුම විවෘත '
            'කරන්න. බැංකුවලින් කරන රීලෝඩ් බැර වීමට විනාඩි කිහිපයක් ගත විය හැකිය. බැංකුවෙන් මුදල් '
            'ගියත් ශේෂය වැඩි නොවූයේ නම්, Clarity ගෙන් අසන්න - එය ගිණුම් විමර්ශනයකි, මෙම ලිපිය නොවේ.'
        ),
        "keywords": ['ශේෂය', 'පරීක්ෂා', 'රීලෝඩ්', 'බැර', 'කොහොමද', 'balance'],
        "language": 'si',
    },
    {
        "article_id": 'KB-FUP-SI',
        "title": 'සාධාරණ භාවිත සීමාව (FUP) යනු කුමක්ද',
        "body": (
            'Unlimited සහ විශාල ඩේටා පැකේජවල මිලදී ගැනීමේදී පෙන්වන සාධාරණ භාවිත සීමාවක් ඇත. එම '
            'ප්\u200dරමාණය භාවිත කළ පසු, වේගය දක්වා ඇති අනුපාතයට අඩු වේ - ඩේටා විසන්ධි නොවේ. සීමාව '
            'සහ සීමාවෙන් පසු වේගය මිලදී ගැනීමට පෙර පැකේජ තිරයේ ඇත. ඔබේ ඩේටා මන්දගාමී නම් සහ මෙම '
            'අංකයේ සීමාව පසු කළාද යන්න දැන ගැනීමට, ඔබේ ගිණුම පරීක්ෂා කරන්න Clarity ගෙන් අසන්න.'
        ),
        "keywords": ['fup', 'සාධාරණ', 'සීමාව', 'මන්දගාමී', 'වේගය', 'unlimited'],
        "language": 'si',
    },
    {
        "article_id": 'KB-VAS-SI',
        "title": 'දායකත්ව සේවා (VAS) කළමනාකරණය',
        "body": (
            'ගෙවිය යුතු දෛනික හෝ මාසික සේවා (ක්\u200dරීඩා, පුවත්, රිංටෝන්) Subscriptions යටතේ '
            'පෙන්වයි. සක්\u200dරිය ඕනෑම එකක් එතැනින් අවලංගු කළ හැකිය. VAS ගාස්තුවක් සඳහා Hutch '
            'විසින් OTP හෝ දෙවන තහවුරු කිරීමේ සාක්ෂි තබා ගත යුතුය. ඔබ කිසි විටෙකත් තහවුරු නොකළ '
            'ගාස්තුවක් දක්නේ නම්, මෙම අංකය පරීක්ෂා කරන්න Clarity ගෙන් අසන්න - එය ගිණුම් නඩුවක් '
            'විවෘත කරයි.'
        ),
        "keywords": ['vas', 'දායකත්ව', 'අවලංගු', 'otp', 'ගාස්තු', 'subscription'],
        "language": 'si',
    },
    {
        "article_id": 'KB-ESIM-TA',
        "title": 'SIM ஐ eSIM ஆக மாற்றுவது அல்லது மாற்றீடு செய்வது',
        "body": (
            'Hutch இயற்பியல் SIM ஐ eSIM ஆக மாற்றவும், அல்லது தொலைந்த eSIM ஐ மாற்றீடு செய்யவும், '
            'Hutch செயலி மூலமாக அல்லது Hutch Experience Centre இல் செய்யலாம்.\n\n1. மாற்ற '
            'விரும்பும் எண்ணில் உள்நுழைக.\n2. மேலும் → SIM / eSIM → eSIM ஆக மாற்று (அல்லது eSIM '
            'மாற்றீடு) என்பதைத் திறக்க.\n3. அந்த எண்ணுக்கு வரும் OTP மூலம் உறுதிப்படுத்துக.\n4. '
            'eSIM வைத்திருக்கும் தொலைபேசியில் QR குறியீட்டை ஸ்கேன் செய்க.\n5. புதிய eSIM Active '
            'எனக் காட்டும் வரை பழைய SIM ஐ வைத்திருக்க.\n\nஉங்கள் எண், இருப்பு மற்றும் தொகுப்புகள் '
            'eSIM உடன் நகரும். தொகுப்புகள் மீண்டும் தொடங்காது. மாற்றம் தோல்வியடைந்தால், இயற்பியல் '
            'SIM ஐப் பயன்படுத்தி, உங்கள் அடையாள அட்டையுடன் Hutch நிலையத்திற்குச் செல்க.'
        ),
        "keywords": ['esim', 'சிம்', 'மாற்று', 'மாற்றீடு', 'எப்படி', 'qr'],
        "language": 'ta',
    },
    {
        "article_id": 'KB-ACTIVATE-PACK-TA',
        "title": 'தரவுத் தொகுப்பை இயக்குவது',
        "body": (
            'இந்த எண்ணில் ஒரு தொகுப்பை இயக்க:\n\n1. Hutch செயலியில் Packages ஐத் திறக்க.\n2. '
            'Anytime, Unlimited, Social, Work அல்லது Combo ஐத் தேர்ந்தெடுக்க.\n3. விலை உங்கள் '
            'முதன்மை இருப்பிலிருந்து கழிக்கப்படும் என உறுதிப்படுத்துக.\n4. உறுதிப்படுத்தல் SMS '
            'வரும் வரை காத்திருக்க. தொகுப்பு Usage இல் காட்டப்படும்.\n\nஇயக்கம் தோல்வியடைந்தால், '
            'அந்த முயற்சிக்கு உங்கள் இருப்பு வைத்துக் கொள்ளப்படாது. மீண்டும் முயற்சிக்க, அல்லது '
            'தொகுப்பு ஏன் இயங்கவில்லை என Clarity இடம் கேட்க - அது கணக்குச் சரிபார்ப்பு, இந்த '
            'வழிகாட்டி அல்ல.'
        ),
        "keywords": ['தொகுப்பு', 'இயக்கு', 'தரவு', 'வாங்க', 'எப்படி', 'activate', 'pack'],
        "language": 'ta',
    },
    {
        "article_id": 'KB-CHECK-BALANCE-TA',
        "title": 'உங்கள் இருப்பைச் சரிபார்ப்பது',
        "body": (
            'உங்கள் முதன்மை இருப்பு Home திரையில் உள்ளது. *#100# ஐ அழைக்க, அல்லது Hutch செயலியைத் '
            'திறக்க. வங்கிகளிலிருந்து வரும் ரீலோட் வரவு வைக்க சில நிமிடங்கள் ஆகலாம். '
            'வங்கியிலிருந்து பணம் போய் இருப்பு உயராவிட்டால், Clarity இடம் கேட்க - அது கணக்கு '
            'விசாரணை, இந்தக் கட்டுரை அல்ல.'
        ),
        "keywords": ['இருப்பு', 'சரிபார்', 'ரீலோட்', 'வரவு', 'எப்படி', 'balance'],
        "language": 'ta',
    },
    {
        "article_id": 'KB-FUP-TA',
        "title": 'நியாயமான பயன்பாட்டு வரம்பு (FUP) என்றால் என்ன',
        "body": (
            'Unlimited மற்றும் பெரிய தரவுத் தொகுப்புகளில், வாங்கும் போது காட்டப்படும் நியாயமான '
            'பயன்பாட்டு வரம்பு உள்ளது. அந்த அளவைப் பயன்படுத்திய பின், வேகம் குறிப்பிட்ட '
            'விகிதத்திற்குக் குறையும் - தரவு துண்டிக்கப்படுவதில்லை. வரம்பும், வரம்புக்குப் பிந்தைய '
            'வேகமும் வாங்கும் முன் தொகுப்புத் திரையில் உள்ளன. உங்கள் தரவு மெதுவாக இருந்து, இந்த '
            'எண்ணில் வரம்பைக் கடந்தீர்களா எனத் தெரிய வேண்டுமானால், உங்கள் கணக்கைச் சரிபார்க்க '
            'Clarity இடம் கேட்க.'
        ),
        "keywords": ['fup', 'நியாயமான', 'வரம்பு', 'மெதுவாக', 'வேகம்', 'unlimited'],
        "language": 'ta',
    },
    {
        "article_id": 'KB-VAS-TA',
        "title": 'சந்தா சேவைகளை (VAS) நிர்வகிப்பது',
        "body": (
            'கட்டணம் செலுத்தும் தினசரி அல்லது மாதாந்திர சேவைகள் (விளையாட்டு, செய்தி, ஒலிக்குறிப்பு)'
            'Subscriptions இல் காட்டப்படும். இயக்கத்தில் உள்ள எதையும் அங்கேயே ரத்து செய்யலாம். ஒரு '
            'VAS கட்டணத்திற்கு Hutch OTP அல்லது இரண்டாம் உறுதிப்படுத்தல் சான்றை வைத்திருக்க '
            'வேண்டும். நீங்கள் ஒருபோதும் உறுதிப்படுத்தாத கட்டணத்தைக் கண்டால், இந்த எண்ணைச் '
            'சரிபார்க்க Clarity இடம் கேட்க - அது ஒரு கணக்கு வழக்கைத் திறக்கும்.'
        ),
        "keywords": ['vas', 'சந்தா', 'ரத்து', 'otp', 'கட்டணம்', 'subscription'],
        "language": 'ta',
    },
]


def classify_intent(question: str) -> str:
    """Return account | knowledge | both for a customer question."""
    text = question.lower()
    knowledge_hints = (
        "how do i",
        "how to",
        "how can i",
        "convert",
        "esim",
        "e-sim",
        "activate a pack",
        "activate pack",
        "what is fup",
        "what does fup",
        "fair use",
        "fair-use",
        "manage subscription",
        "check balance",
        "කොහොමද",
        "எப்படி",
    )
    account_hints = (
        "why",
        "charged",
        "charge",
        "deduct",
        "missing",
        "twice",
        "duplicate",
        "slow",
        "balance change",
        "my data",
        "was i",
        "subscription charge",
        "refund",
        "ඇයි",
        "ஏன்",
        "මන්ද",
        "மெது",
    )
    is_knowledge = any(hint in text for hint in knowledge_hints)
    is_account = any(hint in text for hint in account_hints)
    if is_knowledge and is_account:
        return "both"
    if is_knowledge:
        return "knowledge"
    return "account"

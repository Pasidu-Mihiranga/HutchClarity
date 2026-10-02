/* Hutch self-care. One signed-in account feeds every screen. */

const I18N = {
  en: {
    selfCare: 'Self care',
    signInTitle: 'Sign in with your Hutch number',
    numberLabel: 'Hutch number',
    continue: 'Continue',
    otpTitle: 'Enter the code',
    otpHint: 'We sent a 6-digit code to',
    otpLabel: '6-digit code',
    signIn: 'Sign in',
    back: 'Back',
    welcome: 'Choose how Hutch looks for you',
    notifyLabel: 'Notifications',
    notifyAll: 'Everything',
    notifyImportant: 'Important only',
    notifyNone: 'None',
    largeText: 'Larger text',
    save: 'Save',
    home: 'Home', usage: 'Usage', clarity: 'Clarity', activity: 'Activity', more: 'More',
    hello: 'Hello',
    balance: 'Main balance',
    reload: 'Reload',
    currentPack: 'Current pack',
    dataLeft: 'Data remaining',
    validity: 'Valid for',
    days: '{n} days',
    qaReload: 'Reload', qaPacks: 'Packages', qaSubs: 'Subscriptions', qaUsage: 'Usage', qaSupport: 'Support',
    clarityCard: "Something doesn't look right?",
    clarityAsk: 'Why did my balance change?',
    alerts: 'For you',
    voice: 'Voice', sms: 'SMS', today: 'Today', week: '7 days', month: '30 days',
    packTruth: 'Pack details', price: 'Price', data: 'Data', fup: 'Fair use',
    afterFup: 'After fair use', apps: 'Apps', restrictions: 'Restrictions',
    renewal: 'Renewal', afterExpiry: 'After expiry',
    packages: 'Packages', buy: 'Buy', confirmBuy: 'Confirm purchase',
    notEnough: 'Your balance is not enough for this pack.',
    all: 'All', reloads: 'Reloads', charges: 'Charges', refunds: 'Refunds',
    details: 'Details', askAbout: 'Ask Clarity about this transaction',
    before: 'Balance before', after: 'Balance after', status: 'Status', time: 'Time', category: 'Category',
    subs: 'Subscriptions', cancel: 'Cancel', whySub: 'Why am I subscribed?',
    consent: 'You confirmed this', noConsent: 'No confirmation on file',
    safeguards: 'Safeguards', dataExpiry: 'Data after a pack ends',
    spendCap: 'Spend cap', vasConfirm: 'Confirm subscriptions',
    merchantBlock: 'Block a merchant', usageAlerts: 'Usage alerts',
    stopData: 'Stop data', keepData: 'Keep data on',
    on: 'On', off: 'Off', none: 'None',
    receipts: 'Receipts', cases: 'Cases', open: 'Open', resolved: 'Resolved',
    notifications: 'Notifications', network: 'Network', report: 'Report a problem',
    family: 'Family', addNumber: 'Add a Hutch number', profile: 'Profile',
    language: 'Language', answers: 'Answers', short: 'Short', detailed: 'Detailed',
    terms: 'Terms', privacy: 'Privacy', support: 'Support', signOut: 'Sign out',
    whatHelp: 'What can I help you with?',
    mic: 'Speak', listening: 'Listening…', micMissing: 'Voice input is not available in this browser.',
    composerPh: 'Ask anything…',
    checking: 'Checking your account…',
    canDo: 'What we can do', confirm: 'Confirm', apply: 'Apply the correction',
    getReceipt: 'Get a receipt of this check', nothing: 'Nothing else matched.',
    empty: 'Nothing here yet.',
    noOutage: 'No outage in your area.',
    sent: 'Sent to Hutch staff.',
    done: 'Done. Your receipt is below.',
    working: 'Working…',
    tryAgain: 'Try again',
    amount: 'Amount', id: 'Reference',
    termsBody: 'Hutch self-care shows your balance, packs and charges. Clarity moves money only when you confirm a correction, or when the rules allow an automatic correction. A Trust Receipt records what changed.',
    privacyBody: 'Your number, balance, packs and cases are used to answer the question you asked. Staff see a case only when the rules send it to them.',
    qBalance: 'Why did my balance change?',
    qSub: 'Why am I subscribed?',
    qTwice: 'Why was my reload taken twice?',
    qSlow: 'Why is my data slow?',
    qMissing: "Why didn't my reload arrive?",
    qEsim: 'How do I convert to eSIM?',
    qActivate: 'How do I activate a pack?',
    qFup: 'Why has my speed reduced?',
    qPackIssue: "Why isn't my package working?",
    qPackMissing: "I paid but didn't receive my data",
    qRecommend: 'Which package is best for me?',
    qExpiry: 'What happens when my package expires?',
    qVasList: 'What subscriptions are active?',
    qNetwork: 'Is there a network problem?',
    qRefund: 'What happened to my refund?',
    qCase: "What's happening with my case?",
    qPrevent: 'How can I prevent unexpected charges?',
    chatGreeting: 'Hi {name}, how can Clarity help?',
    chatSubtitle: 'Ask me anything about your Hutch account.',
    suggestedForYou: 'Suggested for you',
    seeMoreTopics: 'See more topics',
    seeFewerTopics: 'Show fewer',
    recentChat: 'Recent',
    foundReason: 'I found the reason',
    whatIChecked: 'What I checked',
    clarityFinding: 'Clarity finding',
    recommendedFix: 'Recommended fix',
    viewEvidence: 'View evidence',
    talkSupport: 'Talk to Support',
    resolvedTitle: 'Resolved',
    viewReceipt: 'View Trust Receipt',
    askAnything: 'Ask anything…',
    askClarityAnything: 'Ask Clarity anything...',
    confidenceLabel: '{n}% confidence',
    clarityBrand: 'Clarity',
    claritySubtitle: 'Hutch AI Assistant',
    chatHi: 'Hi {name}',
    howHelpToday: 'How can I help you today?',
    forYou: 'For you',
    newChat: 'New chat',
    chatHistory: 'History',
    browseTopics: 'Browse topics',
    catMoney: 'Money & Balance',
    catPacks: 'Packages & Data',
    catReloads: 'Reloads',
    catSubs: 'Subscriptions',
    catNetwork: 'Network',
    catEsim: 'SIM & eSIM',
    catProtect: 'Account Protection',
    catSupport: 'Support',
    progUnderstand: 'Understanding your question',
    progCharges: 'Checking recent charges',
    progSubs: 'Checking subscriptions',
    progConsent: 'Checking consent records',
    lookingActivity: 'Looking at your recent activity…',
    refundDisable: 'Refund & Disable',
    confirmDisableTitle: 'Disable {product}?',
    confirmBulletStop: 'Stops the subscription from renewing',
    confirmBulletNoCharge: 'No further daily charges',
    confirmBulletRefund: 'Refunds the disputed amount to your balance',
    thisSubscription: 'this subscription',
    refundedAmount: 'Refunded LKR {amount} to your balance',
    subscriptionDisabled: 'Subscription disabled',
    newBalance: 'New balance: LKR {amount}',
    trustReceipt: 'Trust Receipt',
    verified: 'Verified',
    sentToSpecialist: 'Sent to a specialist',
    viewCase: 'View case',
    needMoreHelp: 'Need more help?',
    couldNotConfirm: 'Could not confirm',
    dataRemaining: 'Data remaining',
    fupActive: 'Fair use cap is active',
    fupOk: 'Within fair use',
    viewUsageDetails: 'View usage details',
    checkNetwork: 'Check network status',
    reportIssue: 'Report an issue',
    accountOk: 'Account status looks normal',
    packOk: 'Pack is active',
    checkLocalSignal: 'Local signal may be weak',
    networkLikely: 'This looks like a coverage issue rather than a billing problem.',
    fuDisable: 'Disable this service',
    fuSubs: 'Show other subscriptions',
    fuPrevent: 'Prevent this happening again',
    fuSupport: 'Talk to support',
    fuFup: 'Check my FUP',
    fuUsage: 'Show remaining data',
    fuBuy: 'Buy another package',
    fuNetwork: 'Check network status',
    fuCompare: 'Compare packages',
    fuDetails: 'Show full details',
    fuActivate: 'Activate package',
    evidenceOk: 'Record found',
    evidenceWarn: 'Valid consent not found',
    evidenceMissing: 'Evidence incomplete',
    human: "I'd rather speak to a person",
    intentNone: 'We checked your account for that, and it is not what we found.',
    intentSlow: 'Your data is not slowed by a fair-use cap right now.',
    intentTwice: 'We did not find a reload that was taken twice on this number.',
    intentMissing: 'We did not find a reload that failed to credit your balance.',
    intentSub: 'We did not find an active subscription charge without your confirmation.',
    intentHint: 'Something else on your account may need a look - try “Why did my balance change?”',
    onThisNumber: 'On this number',
    unknown: 'We could not confirm a single cause from the records we hold.',
    humanFinding: 'A person will pick this up with the full trail - you will not need to repeat anything.',
    caseNo: 'Case {id}',
    actRefund: 'Return LKR {amount} to your balance',
    actOff: 'Switch the subscription off',
    actBlock: 'Block that merchant until you opt in',
    actCap: 'Cap your spending',
    actStop: 'Stop data when a pack ends',
    actAlert: 'Alert you at 80% and 95% of your cap',
    noPack: 'No active pack',
    you: 'You',
    find: 'What we found',
    happened: 'What happened',
    corrected: 'What we corrected',
    protects: 'What protects you now',
    returned: 'Returned',
    chain: 'Chain',
    signed: 'Signed with',
    intact: 'intact',
    notVerified: 'not verified',
    cat_recommended: 'Recommended', cat_anytime: 'Anytime', cat_unlimited: 'Unlimited',
    cat_social: 'Social', cat_work: 'Work and learn', cat_voice: 'Voice', cat_combo: 'Combo',
    packs: {
      'Anytime 5GB': 'Anytime 5GB',
      'Anytime 10GB': 'Anytime 10GB',
      'Unlimited Data': 'Unlimited Data',
      'Social 7 Day': 'Social 7 Day',
      'Work and Learn 15GB': 'Work and Learn 15GB',
      'Voice 200': 'Voice 200',
      'Combo 10GB + 100 min': 'Combo 10GB + 100 min',
      '30-Day Data 10GB': '30-Day Data 10GB'
    }
  },
  si: {
    selfCare: 'ස්වයං සේවාව',
    signInTitle: 'ඔබේ Hutch අංකයෙන් පිවිසෙන්න',
    numberLabel: 'Hutch අංකය',
    continue: 'ඉදිරියට',
    otpTitle: 'කේතය ඇතුළත් කරන්න',
    otpHint: 'ඉලක්කම් 6 ක කේතයක් යැව්වා',
    otpLabel: 'ඉලක්කම් 6 ක කේතය',
    signIn: 'පිවිසෙන්න',
    back: 'ආපසු',
    welcome: 'Hutch ඔබට පෙනෙන ආකාරය තෝරන්න',
    notifyLabel: 'දැනුම්දීම්',
    notifyAll: 'සියල්ල',
    notifyImportant: 'වැදගත් පමණක්',
    notifyNone: 'නැත',
    largeText: 'විශාල අකුරු',
    save: 'සුරකින්න',
    home: 'මුල', usage: 'භාවිතය', clarity: 'Clarity', activity: 'ක්‍රියාකාරකම්', more: 'තවත්',
    hello: 'ආයුබෝවන්',
    balance: 'ප්‍රධාන ශේෂය',
    reload: 'රීලෝඩ්',
    currentPack: 'වත්මන් පැකේජය',
    dataLeft: 'ඉතිරි දත්ත',
    validity: 'වලංගු කාලය',
    days: 'දින {n}',
    qaReload: 'රීලෝඩ්', qaPacks: 'පැකේජ', qaSubs: 'දායකත්ව', qaUsage: 'භාවිතය', qaSupport: 'සහාය',
    clarityCard: 'මොකක්හරි වැරදියිද?',
    clarityAsk: 'මගේ ශේෂය වෙනස් වුණේ ඇයි?',
    alerts: 'ඔබ වෙනුවෙන්',
    voice: 'හඬ', sms: 'SMS', today: 'අද', week: 'දින 7', month: 'දින 30',
    packTruth: 'පැකේජ විස්තර', price: 'මිල', data: 'දත්ත', fup: 'සාධාරණ භාවිතය',
    afterFup: 'ඉන් පසු', apps: 'යෙදුම්', restrictions: 'සීමා',
    renewal: 'අලුත් කිරීම', afterExpiry: 'කල් ඉකුත් වූ පසු',
    packages: 'පැකේජ', buy: 'මිලදී ගන්න', confirmBuy: 'මිලදී ගැනීම තහවුරු කරන්න',
    notEnough: 'මෙම පැකේජයට ඔබේ ශේෂය ප්‍රමාණවත් නැත.',
    all: 'සියල්ල', reloads: 'රීලෝඩ්', charges: 'ගාස්තු', refunds: 'ආපසු ගෙවීම්',
    details: 'විස්තර', askAbout: 'මෙම ගනුදෙනුව ගැන Clarityගෙන් අසන්න',
    before: 'පෙර ශේෂය', after: 'පසු ශේෂය', status: 'තත්වය', time: 'වේලාව', category: 'වර්ගය',
    subs: 'දායකත්ව', cancel: 'අවලංගු කරන්න', whySub: 'මම දායක වුණේ ඇයි?',
    consent: 'ඔබ තහවුරු කළා', noConsent: 'තහවුරු කිරීමක් නැත',
    safeguards: 'ආරක්ෂාව', dataExpiry: 'පැකේජය අවසන් වූ පසු දත්ත',
    spendCap: 'වියදම් සීමාව', vasConfirm: 'දායකත්ව තහවුරු කරන්න',
    merchantBlock: 'වෙළෙන්දෙකු අවහිර කරන්න', usageAlerts: 'භාවිත ඇඟවීම්',
    stopData: 'දත්ත නවත්වන්න', keepData: 'දත්ත තබන්න',
    on: 'සක්‍රිය', off: 'අක්‍රිය', none: 'නැත',
    receipts: 'රිසිට්පත්', cases: 'සිද්ධි', open: 'විවෘත', resolved: 'විසඳුණු',
    notifications: 'දැනුම්දීම්', network: 'ජාලය', report: 'ගැටලුවක් වාර්තා කරන්න',
    family: 'පවුල', addNumber: 'Hutch අංකයක් එක් කරන්න', profile: 'පැතිකඩ',
    language: 'භාෂාව', answers: 'පිළිතුරු', short: 'කෙටි', detailed: 'විස්තරාත්මක',
    terms: 'කොන්දේසි', privacy: 'පෞද්ගලිකත්වය', support: 'සහාය', signOut: 'පිටවෙන්න',
    whatHelp: 'මම ඔබට උදව් කරන්නේ කෙසේද?',
    mic: 'කතා කරන්න', listening: 'අසමින්…', micMissing: 'මෙම බ්‍රව්සරයේ හඬ ඇතුළත් කිරීම නැත.',
    composerPh: 'ගාස්තුවක් ගැන අසන්න',
    checking: 'ඔබේ ගිණුම පරීක්ෂා කරමින්…',
    canDo: 'අපට කළ හැකි දේ', confirm: 'තහවුරු කරන්න', apply: 'නිවැරදි කිරීම යොදන්න',
    getReceipt: 'මෙම පරීක්ෂාවේ රිසිට්පතක් ගන්න', nothing: 'වෙනත් ගැලපීමක් නැත.',
    empty: 'මෙතැන තවම කිසිවක් නැත.',
    noOutage: 'ඔබේ ප්‍රදේශයේ බිඳවැටීමක් නැත.',
    sent: 'Hutch කාර්ය මණ්ඩලයට යැව්වා.',
    done: 'අවසන්. රිසිට්පත පහතින්.',
    working: 'වැඩ කරමින්…',
    tryAgain: 'නැවත උත්සාහ කරන්න',
    amount: 'මුදල', id: 'යොමුව',
    termsBody: 'Hutch ස්වයං සේවාව ඔබේ ශේෂය, පැකේජ සහ ගාස්තු පෙන්වයි. Clarity මුදල් ගෙන යන්නේ ඔබ නිවැරදි කිරීමක් තහවුරු කළ විට හෝ නීති ස්වයංක්‍රීය නිවැරදි කිරීමක් ඉඩ දෙන විට පමණි. Trust Receipt එකක වෙනස සටහන් වේ.',
    privacyBody: 'ඔබ අසන ප්‍රශ්නයට පිළිතුරු දීමට ඔබේ අංකය, ශේෂය, පැකේජ සහ සිද්ධි භාවිත වේ. නීති යවන විට පමණක් කාර්ය මණ්ඩලයට සිද්ධියක් පෙනේ.',
    qBalance: 'මගේ ශේෂය වෙනස් වුණේ ඇයි?',
    qSub: 'මම දායක වුණේ ඇයි?',
    qTwice: 'මගේ රීලෝඩ් දෙවරක් ගත්තේ ඇයි?',
    qSlow: 'මගේ දත්ත මන්දගාමී ඇයි?',
    qMissing: 'මගේ රීලෝඩ් නොආවේ ඇයි?',
    qEsim: 'eSIM එකට මාරු වෙන්නේ කොහොමද?',
    qActivate: 'පැකේජයක් සක්‍රිය කරන්නේ කොහොමද?',
    qFup: 'මගේ වේගය අඩු වුණේ ඇයි?',
    qPackIssue: 'මගේ පැකේජය වැඩ නොකරන්නේ ඇයි?',
    qPackMissing: 'ගෙව්වත් දත්ත ලැබුණේ නැහැ',
    qRecommend: 'මට හොඳම පැකේජය කුමක්ද?',
    qExpiry: 'පැකේජය කල් ඉකුත් වුණාම මොකද වෙන්නේ?',
    qVasList: 'සක්‍රීය දායකත්ව මොනවාද?',
    qNetwork: 'ජාල ගැටලුවක් තිබේද?',
    qRefund: 'මගේ ආපසු ගෙවීමට මොකද වුණේ?',
    qCase: 'මගේ සිද්ධියේ තත්වය කුමක්ද?',
    qPrevent: 'අනපේක්ෂිත අයකිරීම් වළක්වන්නේ කොහොමද?',
    chatGreeting: 'ආයුබෝවන් {name}, Clarity උදව් කරන්නේ කෙසේද?',
    chatSubtitle: 'ඔබේ Hutch ගිණුම ගැන ඕනෑම දෙයක් අසන්න.',
    suggestedForYou: 'ඔබට යෝජිත',
    seeMoreTopics: 'තවත් මාතෘකා',
    seeFewerTopics: 'අඩුවෙන් පෙන්වන්න',
    recentChat: 'මෑත',
    foundReason: 'හේතුව හමු වුණා',
    whatIChecked: 'මම පරීක්ෂා කළේ',
    clarityFinding: 'Clarity සොයාගැනීම',
    recommendedFix: 'නිර්දේශිත නිවැරදි කිරීම',
    viewEvidence: 'සාක්ෂි බලන්න',
    talkSupport: 'සහාය සමඟ කතා කරන්න',
    resolvedTitle: 'විසඳුණා',
    viewReceipt: 'Trust Receipt බලන්න',
    askAnything: 'ඕනෑම දෙයක් අසන්න…',
    askClarityAnything: 'Clarity ගෙන් ඕනෑම දෙයක් අසන්න...',
    confidenceLabel: 'විශ්වාසය {n}%',
    clarityBrand: 'Clarity',
    claritySubtitle: 'Hutch AI සහායක',
    chatHi: 'ආයුබෝවන් {name}',
    howHelpToday: 'අද මම උදව් කරන්නේ කෙසේද?',
    forYou: 'ඔබට',
    newChat: 'නව කතාබස්',
    chatHistory: 'ඉතිහාසය',
    browseTopics: 'මාතෘකා බලන්න',
    catMoney: 'මුදල් සහ ශේෂය',
    catPacks: 'පැකේජ සහ දත්ත',
    catReloads: 'රීලෝඩ්',
    catSubs: 'දායකත්ව',
    catNetwork: 'ජාලය',
    catEsim: 'SIM සහ eSIM',
    catProtect: 'ගිණුම් ආරක්ෂාව',
    catSupport: 'සහාය',
    progUnderstand: 'ඔබේ ප්‍රශ්නය තේරුම් ගනිමින්',
    progCharges: 'මෑත ගාස්තු පරීක්ෂා කරමින්',
    progSubs: 'දායකත්ව පරීක්ෂා කරමින්',
    progConsent: 'අනුමති වාර්තා පරීක්ෂා කරමින්',
    lookingActivity: 'මෑත ක්‍රියාකාරකම් බලමින්…',
    refundDisable: 'ආපසු ගෙවීම සහ අක්‍රිය කරන්න',
    confirmDisableTitle: '{product} අක්‍රිය කරන්නද?',
    confirmBulletStop: 'දායකත්වය අලුත් වීම නවත්වයි',
    confirmBulletNoCharge: 'තවත් දෛනික ගාස්තු නැත',
    confirmBulletRefund: 'විවාදිත මුදල ශේෂයට ආපසු දෙයි',
    thisSubscription: 'මෙම දායකත්වය',
    refundedAmount: 'රු. {amount} ශේෂයට ආපසු දුන්නා',
    subscriptionDisabled: 'දායකත්වය අක්‍රිය කළා',
    newBalance: 'නව ශේෂය: රු. {amount}',
    trustReceipt: 'Trust Receipt',
    verified: 'තහවුරු විය',
    sentToSpecialist: 'විශේෂඥයෙකුට යැව්වා',
    viewCase: 'සිද්ධිය බලන්න',
    needMoreHelp: 'තවත් උදව් අවශ්‍යද?',
    couldNotConfirm: 'තහවුරු කළ නොහැකි විය',
    dataRemaining: 'ඉතිරි දත්ත',
    fupActive: 'සාධාරණ භාවිත සීමාව සක්‍රියයි',
    fupOk: 'සාධාරණ භාවිතය තුළ',
    viewUsageDetails: 'භාවිත විස්තර බලන්න',
    checkNetwork: 'ජාල තත්වය පරීක්ෂා කරන්න',
    reportIssue: 'ගැටලුවක් වාර්තා කරන්න',
    accountOk: 'ගිණුම් තත්වය සාමාන්‍යයි',
    packOk: 'පැකේජය සක්‍රියයි',
    checkLocalSignal: 'දේශීය සංඥාව දුර්වල විය හැක',
    networkLikely: 'මෙය ගාස්තු ගැටලුවකට වඩා ආවරණ ගැටලුවක් ලෙස පෙනේ.',
    fuDisable: 'මෙම සේවාව අක්‍රිය කරන්න',
    fuSubs: 'වෙනත් දායකත්ව පෙන්වන්න',
    fuPrevent: 'නැවත සිදු නොවීමට',
    fuSupport: 'සහාය සමඟ කතා කරන්න',
    fuFup: 'FUP පරීක්ෂා කරන්න',
    fuUsage: 'ඉතිරි දත්ත පෙන්වන්න',
    fuBuy: 'තවත් පැකේජයක් මිලදී ගන්න',
    fuNetwork: 'ජාල තත්වය පරීක්ෂා කරන්න',
    fuCompare: 'පැකේජ සසඳන්න',
    fuDetails: 'සම්පූර්ණ විස්තර',
    fuActivate: 'පැකේජය සක්‍රිය කරන්න',
    evidenceOk: 'වාර්තාව හමු විය',
    evidenceWarn: 'වලංගු අනුමතියක් නැත',
    evidenceMissing: 'සාක්ෂි අසම්පූර්ණයි',
    human: 'මම කෙනෙකුට කතා කිරීමට කැමතියි',
    intentNone: 'අපි ඒ සඳහා ඔබේ ගිණුම පරීක්ෂා කළා. එය අපට හමු වූ දේ නොවේ.',
    intentSlow: 'සාධාරණ භාවිත සීමාව නිසා ඔබේ දත්ත මන්දගාමී නැත.',
    intentTwice: 'දෙවරක් ගත් රීලෝඩ් එකක් මෙම අංකයේ නැත.',
    intentMissing: 'ශේෂයට නොආපු රීලෝඩ් එකක් අපට හමු නොවීය.',
    intentSub: 'තහවුරු කිරීමකින් තොරව සක්‍රිය දායක ගාස්තුවක් නැත.',
    intentHint: 'ඔබේ ගිණුමේ වෙනත් දෙයක් තිබිය හැක - “මගේ ශේෂය වෙනස් වුණේ ඇයි?” අසන්න',
    onThisNumber: 'මෙම අංකයේ',
    unknown: 'අප සතුව ඇති වාර්තා අනුව එක් හේතුවක් තහවුරු කළ නොහැකි විය.',
    humanFinding: 'සම්පූර්ණ තොරතුරු සමඟ පුද්ගලයෙකු මෙය බාර ගනී - ඔබට නැවත කිසිවක් කීමට අවශ්‍ය නැත.',
    caseNo: 'සිද්ධිය {id}',
    actRefund: 'රු. {amount} ඔබේ ශේෂයට ආපසු දෙන්න',
    actOff: 'දායකත්වය නවත්වන්න',
    actBlock: 'ඔබ එකඟ වන තුරු එම වෙළෙන්දා අවහිර කරන්න',
    actCap: 'වියදම සීමා කරන්න',
    actStop: 'පැකේජය අවසන් වූ විට දත්ත නවත්වන්න',
    actAlert: 'සීමාවෙන් 80% සහ 95% දී ඇඟවන්න',
    noPack: 'සක්‍රිය පැකේජයක් නැත',
    you: 'ඔබ',
    find: 'අපට හමු වූ දේ',
    happened: 'සිදු වූ දේ',
    corrected: 'අප නිවැරදි කළ දේ',
    protects: 'දැන් ඔබව ආරක්ෂා කරන දේ',
    returned: 'ආපසු ලැබුණු',
    chain: 'දාමය',
    signed: 'අත්සන් කළේ',
    intact: 'නොබිඳුණු',
    notVerified: 'තහවුරු නොවීය',
    cat_recommended: 'නිර්දේශිත', cat_anytime: 'ඕනෑම වේලාවක', cat_unlimited: 'අසීමිත',
    cat_social: 'සමාජ', cat_work: 'වැඩ සහ ඉගෙනීම', cat_voice: 'හඬ', cat_combo: 'ඒකාබද්ධ',
    packs: {
      'Anytime 5GB': 'ඕනෑම වේලාවක 5GB',
      'Anytime 10GB': 'ඕනෑම වේලාවක 10GB',
      'Unlimited Data': 'අසීමිත දත්ත',
      'Social 7 Day': 'සමාජ දින 7',
      'Work and Learn 15GB': 'වැඩ සහ ඉගෙනීම 15GB',
      'Voice 200': 'හඬ 200',
      'Combo 10GB + 100 min': 'ඒකාබද්ධ 10GB + මිනිත්තු 100',
      '30-Day Data 10GB': 'දින 30 දත්ත 10GB'
    }
  },
  ta: {
    selfCare: 'சுய சேவை',
    signInTitle: 'உங்கள் Hutch எண்ணுடன் நுழையுங்கள்',
    numberLabel: 'Hutch எண்',
    continue: 'தொடரவும்',
    otpTitle: 'குறியீட்டை உள்ளிடுங்கள்',
    otpHint: '6 இலக்க குறியீடு அனுப்பப்பட்டது',
    otpLabel: '6 இலக்க குறியீடு',
    signIn: 'நுழைக',
    back: 'பின்',
    welcome: 'Hutch உங்களுக்கு எப்படி தெரியும் என்பதைத் தேர்ந்தெடுங்கள்',
    notifyLabel: 'அறிவிப்புகள்',
    notifyAll: 'அனைத்தும்',
    notifyImportant: 'முக்கியம் மட்டும்',
    notifyNone: 'வேண்டாம்',
    largeText: 'பெரிய எழுத்து',
    save: 'சேமி',
    home: 'முகப்பு', usage: 'பயன்பாடு', clarity: 'Clarity', activity: 'செயல்பாடு', more: 'மேலும்',
    hello: 'வணக்கம்',
    balance: 'முதன்மை இருப்பு',
    reload: 'ரீலோட்',
    currentPack: 'தற்போதைய பேக்',
    dataLeft: 'மீதமுள்ள தரவு',
    validity: 'செல்லுபடி',
    days: '{n} நாட்கள்',
    qaReload: 'ரீலோட்', qaPacks: 'பேக்குகள்', qaSubs: 'சந்தாக்கள்', qaUsage: 'பயன்பாடு', qaSupport: 'ஆதரவு',
    clarityCard: 'ஏதோ சரியாக இல்லையா?',
    clarityAsk: 'என் இருப்பு ஏன் மாறியது?',
    alerts: 'உங்களுக்காக',
    voice: 'குரல்', sms: 'SMS', today: 'இன்று', week: '7 நாட்கள்', month: '30 நாட்கள்',
    packTruth: 'பேக் விவரம்', price: 'விலை', data: 'தரவு', fup: 'நியாய பயன்பாடு',
    afterFup: 'அதன்பின்', apps: 'செயலிகள்', restrictions: 'கட்டுப்பாடுகள்',
    renewal: 'புதுப்பிப்பு', afterExpiry: 'காலாவதிக்குப் பின்',
    packages: 'பேக்குகள்', buy: 'வாங்கு', confirmBuy: 'வாங்குதலை உறுதிசெய்',
    notEnough: 'இந்த பேக்கிற்கு உங்கள் இருப்பு போதாது.',
    all: 'அனைத்தும்', reloads: 'ரீலோட்கள்', charges: 'கட்டணங்கள்', refunds: 'திரும்பப்பணம்',
    details: 'விவரம்', askAbout: 'இந்த பரிவர்த்தனையைப் பற்றி Clarity இடம் கேளுங்கள்',
    before: 'முந்தைய இருப்பு', after: 'பிந்தைய இருப்பு', status: 'நிலை', time: 'நேரம்', category: 'வகை',
    subs: 'சந்தாக்கள்', cancel: 'ரத்துசெய்', whySub: 'நான் ஏன் சந்தா செய்தேன்?',
    consent: 'நீங்கள் உறுதிசெய்தீர்கள்', noConsent: 'உறுதிப்படுத்தல் இல்லை',
    safeguards: 'பாதுகாப்பு', dataExpiry: 'பேக் முடிந்த பின் தரவு',
    spendCap: 'செலவு வரம்பு', vasConfirm: 'சந்தா உறுதி',
    merchantBlock: 'வணிகரைத் தடு', usageAlerts: 'பயன்பாட்டு எச்சரிக்கை',
    stopData: 'தரவை நிறுத்து', keepData: 'தரவை வைத்திரு',
    on: 'இயக்கு', off: 'நிறுத்து', none: 'இல்லை',
    receipts: 'ரசீதுகள்', cases: 'வழக்குகள்', open: 'திறந்த', resolved: 'தீர்க்கப்பட்டது',
    notifications: 'அறிவிப்புகள்', network: 'வலையமைப்பு', report: 'சிக்கலைப் புகாரளி',
    family: 'குடும்பம்', addNumber: 'ஒரு Hutch எண்ணைச் சேர்', profile: 'சுயவிவரம்',
    language: 'மொழி', answers: 'பதில்கள்', short: 'சுருக்கம்', detailed: 'விரிவான',
    terms: 'விதிகள்', privacy: 'தனியுரிமை', support: 'ஆதரவு', signOut: 'வெளியேறு',
    whatHelp: 'நான் எப்படி உதவட்டும்?',
    mic: 'பேசு', listening: 'கேட்கிறேன்…', micMissing: 'இந்த உலாவியில் குரல் உள்ளீடு இல்லை.',
    composerPh: 'ஒரு கட்டணத்தைப் பற்றி கேளுங்கள்',
    checking: 'உங்கள் கணக்கைச் சரிபார்க்கிறோம்…',
    canDo: 'நாங்கள் செய்யக்கூடியது', confirm: 'உறுதிசெய்', apply: 'திருத்தத்தைப் பயன்படுத்து',
    getReceipt: 'இந்த சரிபார்ப்பின் ரசீதைப் பெறு', nothing: 'வேறு பொருத்தம் இல்லை.',
    empty: 'இங்கே இன்னும் ஒன்றுமில்லை.',
    noOutage: 'உங்கள் பகுதியில் தடை இல்லை.',
    sent: 'Hutch ஊழியர்களுக்கு அனுப்பப்பட்டது.',
    done: 'முடிந்தது. ரசீது கீழே உள்ளது.',
    working: 'செயலாகிறது…',
    tryAgain: 'மீண்டும் முயலவும்',
    amount: 'தொகை', id: 'குறிப்பு',
    termsBody: 'Hutch சுய சேவை உங்கள் இருப்பு, பேக்குகள் மற்றும் கட்டணங்களைக் காட்டுகிறது. நீங்கள் ஒரு திருத்தத்தை உறுதிசெய்யும்போது அல்லது விதிகள் தானியங்கி திருத்தத்தை அனுமதிக்கும்போது மட்டுமே Clarity பணத்தை நகர்த்தும். Trust Receipt மாற்றத்தைப் பதிவு செய்கிறது.',
    privacyBody: 'நீங்கள் கேட்ட கேள்விக்கு பதிலளிக்க உங்கள் எண், இருப்பு, பேக்குகள் மற்றும் வழக்குகள் பயன்படுத்தப்படுகின்றன. விதிகள் அனுப்பும்போது மட்டுமே ஊழியர்கள் ஒரு வழக்கைப் பார்க்கிறார்கள்.',
    qBalance: 'என் இருப்பு ஏன் மாறியது?',
    qSub: 'நான் ஏன் சந்தா செய்தேன்?',
    qTwice: 'என் ரீலோட் ஏன் இரண்டு முறை எடுக்கப்பட்டது?',
    qSlow: 'என் தரவு ஏன் மெதுவாக உள்ளது?',
    qMissing: 'என் ரீலோட் ஏன் வரவில்லை?',
    qEsim: 'eSIM-க்கு எப்படி மாறுவது?',
    qActivate: 'பேக்கை எப்படி செயல்படுத்துவது?',
    qFup: 'என் வேகம் ஏன் குறைந்தது?',
    qPackIssue: 'என் பேக் ஏன் வேலை செய்யவில்லை?',
    qPackMissing: 'பணம் செலுத்தினும் தரவு வரவில்லை',
    qRecommend: 'எனக்கு சிறந்த பேக் எது?',
    qExpiry: 'பேக் காலாவதியாகும்போது என்ன ஆகும்?',
    qVasList: 'எந்த சந்தாக்கள் செயலில் உள்ளன?',
    qNetwork: 'நெட்வொர்க் பிரச்சனையா?',
    qRefund: 'என் திரும்பப்பணத்திற்கு என்ன ஆனது?',
    qCase: 'என் வழக்கின் நிலை என்ன?',
    qPrevent: 'எதிர்பாராத கட்டணங்களை எப்படித் தடுப்பது?',
    chatGreeting: 'வணக்கம் {name}, Clarity எப்படி உதவட்டும்?',
    chatSubtitle: 'உங்கள் Hutch கணக்கு பற்றி எதையும் கேளுங்கள்.',
    suggestedForYou: 'உங்களுக்கான பரிந்துரைகள்',
    seeMoreTopics: 'மேலும் தலைப்புகள்',
    seeFewerTopics: 'குறைவாகக் காட்டு',
    recentChat: 'சமீபத்தியவை',
    foundReason: 'காரணம் கிடைத்தது',
    whatIChecked: 'நான் சரிபார்த்தவை',
    clarityFinding: 'Clarity கண்டுபிடிப்பு',
    recommendedFix: 'பரிந்துரைக்கப்பட்ட தீர்வு',
    viewEvidence: 'ஆதாரத்தைப் பார்',
    talkSupport: 'ஆதரவிடம் பேசு',
    resolvedTitle: 'தீர்க்கப்பட்டது',
    viewReceipt: 'Trust Receipt பார்',
    askAnything: 'எதையும் கேளுங்கள்…',
    askClarityAnything: 'Clarity இடம் எதையும் கேளுங்கள்...',
    confidenceLabel: 'நம்பிக்கை {n}%',
    clarityBrand: 'Clarity',
    claritySubtitle: 'Hutch AI உதவியாளர்',
    chatHi: 'வணக்கம் {name}',
    howHelpToday: 'இன்று நான் எப்படி உதவட்டும்?',
    forYou: 'உங்களுக்கு',
    newChat: 'புதிய அரட்டை',
    chatHistory: 'வரலாறு',
    browseTopics: 'தலைப்புகளைப் பார்',
    catMoney: 'பணம் & இருப்பு',
    catPacks: 'பேக்குகள் & தரவு',
    catReloads: 'ரீலோட்கள்',
    catSubs: 'சந்தாக்கள்',
    catNetwork: 'நெட்வொர்க்',
    catEsim: 'SIM & eSIM',
    catProtect: 'கணக்குப் பாதுகாப்பு',
    catSupport: 'ஆதரவு',
    progUnderstand: 'உங்கள் கேள்வியைப் புரிந்துகொள்கிறேன்',
    progCharges: 'சமீபத்திய கட்டணங்களைச் சரிபார்க்கிறேன்',
    progSubs: 'சந்தாக்களைச் சரிபார்க்கிறேன்',
    progConsent: 'ஒப்புதல் பதிவுகளைச் சரிபார்க்கிறேன்',
    lookingActivity: 'சமீபத்திய செயல்பாட்டைப் பார்க்கிறேன்…',
    refundDisable: 'திரும்பப்பணம் & நிறுத்து',
    confirmDisableTitle: '{product} நிறுத்தவா?',
    confirmBulletStop: 'சந்தா புதுப்பிப்பை நிறுத்தும்',
    confirmBulletNoCharge: 'மேலும் தினசரி கட்டணம் இல்லை',
    confirmBulletRefund: 'விவாதத் தொகையை இருப்பிற்குத் திருப்பும்',
    thisSubscription: 'இந்த சந்தா',
    refundedAmount: 'ரூ. {amount} இருப்பிற்குத் திருப்பப்பட்டது',
    subscriptionDisabled: 'சந்தா நிறுத்தப்பட்டது',
    newBalance: 'புதிய இருப்பு: ரூ. {amount}',
    trustReceipt: 'Trust Receipt',
    verified: 'சரிபார்க்கப்பட்டது',
    sentToSpecialist: 'நிபுணரிடம் அனுப்பப்பட்டது',
    viewCase: 'வழக்கைப் பார்',
    needMoreHelp: 'மேலும் உதவி வேண்டுமா?',
    couldNotConfirm: 'உறுதிப்படுத்த முடியவில்லை',
    dataRemaining: 'மீதமுள்ள தரவு',
    fupActive: 'நியாய பயன்பாட்டு வரம்பு செயலில்',
    fupOk: 'நியாய பயன்பாட்டிற்குள்',
    viewUsageDetails: 'பயன்பாட்டு விவரம்',
    checkNetwork: 'நெட்வொர்க் நிலையைச் சரிபார்',
    reportIssue: 'சிக்கலைப் புகாரளி',
    accountOk: 'கணக்கு நிலை சாதாரணம்',
    packOk: 'பேக் செயலில் உள்ளது',
    checkLocalSignal: 'உள்ளூர் சமிக்ஞை பலவீனமாக இருக்கலாம்',
    networkLikely: 'இது கட்டணச் சிக்கலை விட கவரேஜ் சிக்கல் போல் தெரிகிறது.',
    fuDisable: 'இந்த சேவையை நிறுத்து',
    fuSubs: 'பிற சந்தாக்களைக் காட்டு',
    fuPrevent: 'மீண்டும் நடக்காமல் தடு',
    fuSupport: 'ஆதரவிடம் பேசு',
    fuFup: 'FUP சரிபார்',
    fuUsage: 'மீதமுள்ள தரவைக் காட்டு',
    fuBuy: 'மற்றொரு பேக் வாங்கு',
    fuNetwork: 'நெட்வொர்க் நிலையைச் சரிபார்',
    fuCompare: 'பேக்குகளை ஒப்பிடு',
    fuDetails: 'முழு விவரம்',
    fuActivate: 'பேக்கைச் செயல்படுத்து',
    evidenceOk: 'பதிவு கிடைத்தது',
    evidenceWarn: 'செல்லுபடியாகும் ஒப்புதல் இல்லை',
    evidenceMissing: 'ஆதாரம் முழுமையற்றது',
    human: 'ஒரு நபரிடம் பேச விரும்புகிறேன்',
    intentNone: 'அதற்காக உங்கள் கணக்கைச் சரிபார்த்தோம். அது நாங்கள் கண்டது அல்ல.',
    intentSlow: 'நியாய பயன்பாட்டு வரம்பால் உங்கள் தரவு மெதுவாக இல்லை.',
    intentTwice: 'இந்த எண்ணில் இரண்டு முறை எடுக்கப்பட்ட ரீலோட் இல்லை.',
    intentMissing: 'இருப்புக்கு வராத ரீலோட்டை நாங்கள் காணவில்லை.',
    intentSub: 'உறுதிப்படுத்தல் இல்லாத செயலில் உள்ள சந்தா கட்டணம் இல்லை.',
    intentHint: 'உங்கள் கணக்கில் வேறு ஏதோ இருக்கலாம் - “என் இருப்பு ஏன் மாறியது?” என்று கேளுங்கள்',
    onThisNumber: 'இந்த எண்ணில்',
    unknown: 'எங்களிடம் உள்ள பதிவுகளில் இருந்து ஒரு காரணத்தை உறுதிப்படுத்த முடியவில்லை.',
    humanFinding: 'முழு விவரங்களுடன் ஒருவர் இதை எடுத்துக்கொள்வார் - நீங்கள் மீண்டும் எதுவும் சொல்ல வேண்டியதில்லை.',
    caseNo: 'வழக்கு {id}',
    actRefund: 'ரூ. {amount} உங்கள் இருப்பிற்குத் திருப்பவும்',
    actOff: 'சந்தாவை நிறுத்தவும்',
    actBlock: 'நீங்கள் ஒப்புக்கொள்ளும் வரை அந்த வணிகரைத் தடுக்கவும்',
    actCap: 'செலவை வரம்பிடவும்',
    actStop: 'பேக் முடிந்ததும் தரவை நிறுத்தவும்',
    actAlert: 'வரம்பின் 80% மற்றும் 95% இல் எச்சரிக்கவும்',
    noPack: 'செயலில் உள்ள பேக் இல்லை',
    you: 'நீங்கள்',
    find: 'நாங்கள் கண்டது',
    happened: 'என்ன நடந்தது',
    corrected: 'நாங்கள் சரிசெய்தது',
    protects: 'இப்போது உங்களைப் பாதுகாப்பது',
    returned: 'திரும்பக் கிடைத்தது',
    chain: 'சங்கிலி',
    signed: 'கையொப்பம்',
    intact: 'முழுமையானது',
    notVerified: 'சரிபார்க்கப்படவில்லை',
    cat_recommended: 'பரிந்துரை', cat_anytime: 'எப்போதும்', cat_unlimited: 'வரம்பற்ற',
    cat_social: 'சமூகம்', cat_work: 'வேலை மற்றும் கற்றல்', cat_voice: 'குரல்', cat_combo: 'கூட்டு',
    packs: {
      'Anytime 5GB': 'எப்போதும் 5GB',
      'Anytime 10GB': 'எப்போதும் 10GB',
      'Unlimited Data': 'வரம்பற்ற தரவு',
      'Social 7 Day': 'சமூக 7 நாள்',
      'Work and Learn 15GB': 'வேலை மற்றும் கற்றல் 15GB',
      'Voice 200': 'குரல் 200',
      'Combo 10GB + 100 min': 'கூட்டு 10GB + 100 நிமிடம்',
      '30-Day Data 10GB': '30 நாள் தரவு 10GB'
    }
  }
};

const DEMO_USERS = [
  { name: 'Dilani', number: '0771234567' },
  { name: 'Nimal', number: '0772223333' },
  { name: 'Kavitha', number: '0773334444' },
  { name: 'Priya', number: '0774445555' }
];

let lang = 'en';
let appState = null;
let view = 'login';
let pending = { msisdn: null, challenge: null, sentTo: '' };
let filter = 'all';
let usageWindow = '7';
let selectedPack = null;
let selectedTxn = null;
let answerMode = 'short';
let onboard = { notify: 'important', large: false };
let clarityState = {
  mode: null,
  decision: null,
  timeline: null,
  caseId: null,
  planId: null,
  chargeRef: null,
  receipt: null,
  receiptDoc: null,
  receiptCheck: null,
  question: '',
  intent: null,
  chatIntent: null,
  articles: null,
  followUps: [],
  messages: [],
  suggestions: [],
  moreTopics: [],
  showMore: false,
  turnReply: null,
  threadId: null,
  contextProduct: null,
  contextAmount: null
};
let recognition = null;

const INTENT_EMPTY = {
  balance: 'intentNone',
  sub: 'intentSub',
  twice: 'intentTwice',
  slow: 'intentSlow',
  missing: 'intentMissing'
};

const SUGGESTED = [
  { key: 'qBalance', intent: 'balance', chatIntent: 'BALANCE_DEDUCTION_QUERY' },
  { key: 'qSub', intent: 'sub', chatIntent: 'UNEXPECTED_CHARGE' },
  { key: 'qTwice', intent: 'twice', chatIntent: 'DOUBLE_CHARGE' },
  { key: 'qSlow', intent: 'slow', chatIntent: 'DATA_SLOW' },
  { key: 'qMissing', intent: 'missing', chatIntent: 'RELOAD_MISSING' },
  { key: 'qEsim', intent: 'knowledge', chatIntent: 'ESIM_HELP' },
  { key: 'qActivate', intent: 'knowledge', chatIntent: 'PACK_ACTIVATE' },
  { key: 'qFup', intent: 'slow', chatIntent: 'FUP_QUERY' },
  { key: 'qRecommend', intent: 'knowledge', chatIntent: 'PACK_RECOMMEND' },
  { key: 'qPrevent', intent: 'knowledge', chatIntent: 'PREVENT_CHARGES' },
  { key: 'qVasList', intent: 'sub', chatIntent: 'VAS_SUBSCRIPTIONS' },
  { key: 'qNetwork', intent: 'knowledge', chatIntent: 'NETWORK_STATUS' },
  { key: 'qExpiry', intent: 'balance', chatIntent: 'PACK_EXPIRY' },
  { key: 'qPackIssue', intent: 'slow', chatIntent: 'PACK_NOT_WORKING' },
  { key: 'qPackMissing', intent: 'missing', chatIntent: 'PACK_MISSING' },
  { key: 'qRefund', intent: 'balance', chatIntent: 'REFUND_STATUS' },
  { key: 'qCase', intent: 'balance', chatIntent: 'CASE_STATUS' }
];

const DEFAULT_CHIP_KEYS = ['qBalance', 'qSlow', 'qRecommend', 'qEsim', 'qSub', 'qPrevent'];

function activityRows() {
  return (appState && appState.activity) || [];
}

function accountIntents() {
  const rows = activityRows();
  const pack = appState && appState.pack;
  const subs = (appState && appState.subscriptions) || [];
  const payments = rows.filter(row => row.type === 'payment_captured');
  const credits = rows.filter(row => row.type === 'balance_credited' && row.detail !== 'clarity_refund');
  const counts = {};
  for (const row of payments) {
    const key = String(row.amount_lkr || '');
    counts[key] = (counts[key] || 0) + 1;
  }
  const twice = Object.values(counts).some(count => count >= 2);
  const missing = payments.some(pay =>
    !credits.some(credit => String(credit.amount_lkr) === String(pay.amount_lkr))
  );
  const sub = subs.some(item => item.active && !item.consent) || rows.some(row => row.type === 'vas_charge');
  const slow = (pack && pack.used_pct != null && pack.used_pct >= 80)
    || rows.some(row => row.type === 'fup_cap_reached' || row.type === 'throttle_applied');
  const balance = sub || twice || missing || slow
    || rows.some(row => ['charges', 'reloads', 'refunds'].includes(row.bucket));
  return { sub, twice, missing, slow, balance, knowledge: true };
}

function intentForQuestion(questionKey, freeText) {
  const suggested = SUGGESTED.find(item => item.key === questionKey);
  if (suggested) return suggested.intent;
  const text = String(freeText || '').toLowerCase();
  if (/esim|e-sim|convert|activate a pack|how do i|how to|කොහොමද|எப்படி/.test(text)) return 'knowledge';
  if (/subscri|දායක|சந்தா/.test(text)) return 'sub';
  if (/twice|duplicate|දෙවර|இரண்டு/.test(text)) return 'twice';
  if (/slow|fup|මන්ද|மெது/.test(text)) return 'slow';
  if (/arriv|missing|credit|නොආ|வரவில்லை/.test(text)) return 'missing';
  return 'balance';
}

function chargeForIntent(intent) {
  const rows = activityRows();
  const pick = (test) => {
    const row = rows.find(test);
    return row ? row.id : null;
  };
  if (intent === 'sub') return pick(row => row.type === 'vas_charge' || row.bucket === 'charges');
  if (intent === 'twice' || intent === 'missing') return pick(row => row.type === 'payment_captured');
  if (intent === 'slow') {
    return pick(row => row.type === 'fup_cap_reached' || row.type === 'throttle_applied' || row.bucket === 'usage');
  }
  return pick(row => ['charges', 'reloads', 'refunds'].includes(row.bucket));
}

const T = (key) => (I18N[lang] && I18N[lang][key]) || I18N.en[key] || key;
const packLabel = (name) => (I18N[lang].packs && I18N[lang].packs[name]) || name;
const lkr = (value) => value == null || value === '' ? '' : `LKR ${value}`;
const htmlLang = () => (lang === 'si' ? 'si' : lang === 'ta' ? 'ta' : 'en');

function go(next) {
  view = next;
  const hash = '#' + next;
  if (location.hash !== hash) history.pushState({ view: next }, '', hash);
  render();
}

function paintChrome() {
  const authed = signedIn() && appState && appState.onboarded && !['login', 'otp', 'onboard'].includes(view);
  const immersive = authed && view === 'clarity';
  document.getElementById('brandSub').textContent = authed ? `${appState.name} · ${appState.masked}` : T('selfCare');
  document.getElementById('langSlot').innerHTML = ['en', 'si', 'ta'].map(code => {
    const label = code === 'en' ? 'English' : code === 'si' ? 'සිංහල' : 'தமிழ்';
    return `<button type="button" data-lang="${code}" class="${lang === code ? 'on' : ''}">${label}</button>`;
  }).join('');
  document.getElementById('langSlot').className = 'seg';
  const nav = document.getElementById('tabbar');
  nav.classList.toggle('hidden', !authed || immersive);
  document.body.classList.toggle('no-nav', !authed || immersive);
  document.body.classList.toggle('clarity-immersive', immersive);
  if (!immersive && window.ClarityChat) ClarityChat.unmount();
  const compose = immersive;
  document.getElementById('composerForm').classList.toggle('hidden', !compose);
  document.body.classList.toggle('no-compose', !compose);
  const composerInput = document.getElementById('composerInput');
  if (composerInput) composerInput.placeholder = immersive ? T('askClarityAnything') : T('askAnything');
  const tab = ['packages', 'package', 'subs', 'safeguards', 'receipts', 'receipt', 'cases', 'notifications', 'network', 'family', 'profile', 'terms', 'privacy'].includes(view)
    ? 'more' : (view === 'txn' ? 'activity' : view);
  nav.querySelectorAll('button').forEach(button => {
    button.classList.toggle('active', button.dataset.go === tab);
    const label = button.querySelector('.tab-label');
    if (label) label.textContent = T(button.dataset.go);
  });
  document.getElementById('mic').textContent = T('mic');
  document.getElementById('mic').setAttribute('aria-label', T('mic'));
  document.documentElement.lang = htmlLang();
  document.body.classList.toggle('large-text', !!(appState && appState.large_text));
}

function render() {
  window.scrollTo(0, 0);
  paintChrome();
  const screen = document.getElementById('screen');
  if (view === 'clarity' && window.ClarityChat) {
    ClarityChat.mount();
    return;
  }
  const pages = {
    login: loginHtml, otp: otpHtml, onboard: onboardHtml, home: homeHtml, usage: usageHtml,
    clarity: clarityHtml, activity: activityHtml, txn: txnHtml, more: moreHtml, reload: reloadHtml,
    packages: packagesHtml, package: packageHtml, subs: subsHtml, safeguards: safeHtml,
    receipts: receiptsHtml, receipt: receiptHtml, cases: casesHtml, notifications: notesHtml,
    network: networkHtml, family: familyHtml, profile: profileHtml, terms: termsHtml, privacy: privacyHtml
  };
  screen.innerHTML = (pages[view] || loginHtml)();
  if (view === 'receipt' && clarityState.receiptDoc) paintReceipt(clarityState.receiptDoc, clarityState.receiptCheck);
}

function loginHtml() {
  return `<h1 class="greeting">${esc(T('signInTitle'))}</h1>
    <form id="loginForm" class="card">
      <label class="field">${esc(T('numberLabel'))}
        <input id="msisdn" inputmode="tel" autocomplete="tel" placeholder="077 123 4567" required>
      </label>
      <button class="btn-primary" type="submit">${esc(T('continue'))}</button>
      <div class="demo-users" role="group" aria-label="Accounts">
        ${DEMO_USERS.map(user => `
          <button type="button" class="demo-user" data-act="fill-number" data-number="${esc(user.number)}">
            <strong>${esc(user.name)}</strong>
            <span class="mono">${esc(user.number)}</span>
          </button>`).join('')}
      </div>
    </form>`;
}

function otpHtml() {
  return `<h1 class="greeting">${esc(T('otpTitle'))}</h1>
    <form id="otpForm" class="card">
      <p class="sub">${esc(T('otpHint'))} <span class="mono">${esc(pending.sentTo)}</span></p>
      <label class="field">${esc(T('otpLabel'))}
        <input id="otp" class="otp-input" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required>
      </label>
      <div class="btn-row">
        <button class="btn-primary" type="submit">${esc(T('signIn'))}</button>
        <button class="btn-ghost" type="button" data-act="back-login">${esc(T('back'))}</button>
      </div>
    </form>`;
}

function onboardHtml() {
  return `<h1 class="greeting">${esc(T('welcome'))}</h1>
    <form id="onboardForm" class="card">
      <p class="sub">${esc(T('language'))}</p>
      <div class="seg" style="margin-bottom:14px">
        ${['en', 'si', 'ta'].map(code => `<button type="button" data-lang="${code}" class="${lang === code ? 'on' : ''}">${code === 'en' ? 'English' : code === 'si' ? 'සිංහල' : 'தமிழ்'}</button>`).join('')}
      </div>
      <label class="field">${esc(T('notifyLabel'))}
        <select id="notify">
          <option value="all" ${onboard.notify === 'all' ? 'selected' : ''}>${esc(T('notifyAll'))}</option>
          <option value="important" ${onboard.notify === 'important' ? 'selected' : ''}>${esc(T('notifyImportant'))}</option>
          <option value="none" ${onboard.notify === 'none' ? 'selected' : ''}>${esc(T('notifyNone'))}</option>
        </select>
      </label>
      <label class="field"><span><input id="large" type="checkbox" ${onboard.large ? 'checked' : ''}> ${esc(T('largeText'))}</span></label>
      <button class="btn-primary" type="submit">${esc(T('save'))}</button>
    </form>`;
}

function homeHtml() {
  const a = appState;
  const pack = a.pack;
  const pct = pack && pack.used_pct != null ? Math.min(pack.used_pct, 100) : 0;
  const left = pack && pack.data_gb && pack.used_gb
    ? (Number(pack.data_gb) - Number(pack.used_gb)).toFixed(2)
    : (pack && pack.data_gb ? pack.data_gb : ' - ');
  return `<p class="sub" style="margin-bottom:4px">${esc(T('hello'))}</p>
    <h1 class="greeting" style="margin-top:0">${esc(a.name || a.masked)}</h1>
    <p class="mono sub">${esc(a.masked)}</p>
    <section class="balance-card">
      <div class="sub">${esc(T('balance'))}</div>
      <div class="amount">${esc(lkr(a.balance_lkr))}</div>
      <button class="btn-primary" type="button" data-act="go" data-view="reload" style="margin-top:12px">${esc(T('reload'))}</button>
    </section>
    <section class="soft-card">
      <div class="sub">${esc(T('currentPack'))}</div>
      <strong>${esc(pack ? packLabel(pack.name) : T('noPack'))}</strong>
      ${pack ? `<p class="sub">${esc(T('dataLeft'))}: ${esc(left)} GB · ${esc(T('validity'))} ${esc(T('days').replace('{n}', pack.days_left))}</p>
        <div class="fup-track"><div class="fup-fill" style="width:${pct}%"></div></div>` : ''}
    </section>
    <div class="quick">
      ${[['reload', 'qaReload'], ['packages', 'qaPacks'], ['subs', 'qaSubs'], ['usage', 'qaUsage'], ['cases', 'qaSupport']].map(([dest, key]) =>
        `<button type="button" data-act="go" data-view="${dest}">${esc(T(key))}</button>`).join('')}
    </div>
    <button type="button" class="hero-prompt" data-act="ask" data-q="qBalance">
      <div class="hero-copy"><strong>${esc(T('clarityCard'))}</strong><span class="hero-desc">${esc(T('clarityAsk'))}</span></div>
      <span class="hero-go" aria-hidden="true">→</span>
    </button>
    ${a.alerts.length ? `<h3>${esc(T('alerts'))}</h3>` + a.alerts.map(alert =>
      `<button type="button" class="menu-row" data-act="ask" data-q="qBalance">${esc(alert.text)}</button>`).join('') : ''}`;
}

function usageHtml() {
  const a = appState;
  const pack = a.pack;
  const rows = windowed(a.activity.filter(row => row.bucket === 'usage' || row.bucket === 'packages'));
  return `<h1 class="greeting">${esc(T('usage'))}</h1>
    <div class="stat-grid">
      <div><span class="sub">${esc(T('data'))}</span><strong>${esc(a.usage.data_used_gb || '0')} GB</strong></div>
      <div><span class="sub">${esc(T('voice'))}</span><strong>${esc(a.usage.voice_minutes)} min</strong></div>
      <div><span class="sub">${esc(T('sms'))}</span><strong>${esc(a.usage.sms)}</strong></div>
    </div>
    <div class="chip-row">
      ${[['1', 'today'], ['7', 'week'], ['30', 'month']].map(([value, key]) =>
        `<button type="button" class="chip ${usageWindow === value ? 'on' : ''}" data-act="window" data-window="${value}">${esc(T(key))}</button>`).join('')}
    </div>
    ${rows.length ? rows.map(row => `<div class="menu-row"><span>${esc(row.detail)}</span><span class="sub">${esc(fmtDate(row.at))}</span></div>`).join('') : `<p class="sub">${esc(T('empty'))}</p>`}
    ${pack ? packTruth(pack) : ''}`;
}

function packTruth(pack) {
  const rows = [
    [T('price'), lkr(pack.price_lkr)],
    [T('data'), pack.data_gb ? `${pack.data_gb} GB` : ' - '],
    [T('validity'), T('days').replace('{n}', pack.days_left)],
    [T('fup'), pack.used_pct != null ? `${pack.used_pct}%` : ' - '],
    [T('afterFup'), pack.after_cap_speed || ' - '],
    [T('apps'), pack.apps || ' - '],
    [T('restrictions'), pack.restrictions || ' - '],
    [T('renewal'), pack.renewal || ' - '],
    [T('afterExpiry'), pack.after_expiry || ' - ']
  ];
  return `<h3>${esc(T('packTruth'))}</h3><dl class="kv">${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`;
}

function windowed(rows) {
  const days = Number(usageWindow);
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  return rows.filter(row => new Date(row.at).getTime() >= cutoff);
}

function clarityHtml() {
  return `<div class="clarity-chat-kodee"></div>`;
}

async function loadSuggestions() {
  const box = document.getElementById('suggestionChips');
  const more = document.getElementById('moreTopics');
  if (!box) return;
  try {
    const payload = await api('/v1/conversation/suggestions', 'POST', {
      language: lang,
      limit: 6,
      snapshot: {
        pack: appState.pack || {},
        subscriptions: appState.subscriptions || [],
        activity: appState.activity || [],
        open_case: (appState.cases || []).some(c => c.status === 'open')
      }
    });
    clarityState.suggestions = payload.suggestions || [];
    clarityState.moreTopics = payload.more_topics || [];
  } catch (_error) {
    clarityState.suggestions = DEFAULT_CHIP_KEYS.map(key => {
      const item = SUGGESTED.find(s => s.key === key);
      return { id: key, i18n_key: key, intent: item ? item.chatIntent : 'BALANCE_DEDUCTION_QUERY', reason: 'default' };
    });
    clarityState.moreTopics = SUGGESTED.filter(s => !DEFAULT_CHIP_KEYS.includes(s.key)).map(s => ({
      id: s.key, i18n_key: s.key, intent: s.chatIntent
    }));
  }
  paintSuggestionChips();
}

function paintSuggestionChips() {
  const box = document.getElementById('suggestionChips');
  const more = document.getElementById('moreTopics');
  const btn = document.getElementById('moreTopicsBtn');
  if (!box) return;
  const chipHtml = (chip) => {
    const label = chip.label || T(chip.i18n_key) || chip.id;
    const qKey = chip.i18n_key || chip.id;
    return `<button type="button" class="chip suggestion-chip" data-act="ask" data-q="${esc(qKey)}" data-intent="${esc(chip.intent || '')}">${esc(label)}</button>`;
  };
  box.innerHTML = (clarityState.suggestions || []).map(chipHtml).join('');
  if (more) {
    more.innerHTML = (clarityState.moreTopics || []).map(chipHtml).join('');
    more.classList.toggle('hidden', !clarityState.showMore);
  }
  if (btn) btn.textContent = T(clarityState.showMore ? 'seeFewerTopics' : 'seeMoreTopics');
}

function paintTranscript() {
  const box = document.getElementById('chatTranscript');
  if (!box) return;
  if (!clarityState.messages.length) {
    box.innerHTML = '';
    return;
  }
  box.innerHTML = clarityState.messages.map((msg, index) => {
    if (msg.role === 'user') {
      return `<div class="chat-bubble user"><span class="chat-who">${esc(T('you'))}</span><p>${esc(msg.text)}</p></div>`;
    }
    return `<div class="chat-bubble clarity" data-msg="${index}">${msg.html}</div>`;
  }).join('');
  const last = box.lastElementChild;
  if (last) last.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  // Rebind offer buttons inside last result card
  const offer = box.querySelector('#offer');
  if (offer && clarityState.decision) fillOffer(clarityState.decision);
}

function evidenceChecklist(decision, timeline) {
  const sources = (timeline && timeline.sources) || [];
  const items = [];
  if (sources.length) {
    for (const src of sources.slice(0, 5)) {
      const name = src.source || src.name || 'source';
      const status = (src.completeness || src.status || '').toLowerCase();
      if (status === 'missing' || status === 'partial') {
        items.push({ ok: false, warn: status === 'partial', text: `${name}: ${T('evidenceMissing')}` });
      } else {
        items.push({ ok: true, warn: false, text: `${name}: ${T('evidenceOk')}` });
      }
    }
  }
  const rule = decision && (decision.matched_rule || decision.rule_id);
  if (rule && /VAS|CONSENT|NO_CONSENT/i.test(String(rule))) {
    items.push({ ok: false, warn: true, text: T('evidenceWarn') });
  }
  if (!items.length) {
    items.push({ ok: true, warn: false, text: T('evidenceOk') });
  }
  return `<ul class="evidence-list">${items.map(item => {
    const mark = item.ok && !item.warn ? '✓' : '⚠';
    const cls = item.ok && !item.warn ? 'ok' : 'warn';
    return `<li class="${cls}"><span>${mark}</span> ${esc(item.text)}</li>`;
  }).join('')}</ul>`;
}

function followUpHtml(followUps) {
  if (!followUps || !followUps.length) return '';
  return `<div class="chip-row follow-ups">${followUps.map(fu => {
    const label = T(fu.i18n_key) || fu.id;
    return `<button type="button" class="chip" data-act="follow" data-intent="${esc(fu.intent || '')}" data-key="${esc(fu.i18n_key || '')}">${esc(label)}</button>`;
  }).join('')}</div>`;
}

function buildResultCardHtml() {
  const d = clarityState.decision || {};
  const timeline = clarityState.timeline || { events: [], sources: [] };
  const outcome = d.outcome || 'HANDOFF';
  const finding = d.explanation || T('unknown');
  const amount = d.amount_lkr ? lkr(d.amount_lkr) : '';
  const conf = d.confidence != null ? T('confidenceLabel').replace('{n}', Math.round(Number(d.confidence) * (Number(d.confidence) <= 1 ? 100 : 1))) : '';
  const caseLabel = clarityState.caseId ? T('caseNo').replace('{id}', clarityState.caseId) : '';
  const detail = answerMode === 'detailed' ? `
    <ul class="why-list">${(d.rationale || []).map(line => `<li>${esc(line)}</li>`).join('')}</ul>
    <h3>${esc(T('find'))}</h3>
    <ul class="why-list">${(timeline.events || []).map(event => `<li>${esc(describe(event))} · ${esc(fmtDate(event.occurred_at))}</li>`).join('')}</ul>
  ` : '';
  return `<div class="result-card">
    <p class="card-title">${esc(T('foundReason'))}</p>
    ${amount ? `<p class="card-amount"><strong>${esc(amount)}</strong></p>` : ''}
    <span class="verdict v-${esc(outcome)}">${esc(String(outcome).replace(/_/g, ' '))}</span>
    <h3>${esc(T('whatIChecked'))}</h3>
    ${evidenceChecklist(d, timeline)}
    <h3>${esc(T('clarityFinding'))}</h3>
    <p>${esc(clarityState.mode === 'human' ? T('humanFinding') : finding)}</p>
    ${conf ? `<p class="sub">${esc(conf)}</p>` : ''}
    ${caseLabel ? `<p class="sub">${esc(caseLabel)}</p>` : ''}
    ${detail}
    <button type="button" class="btn-ghost" data-act="toggle-evidence">${esc(T('viewEvidence'))}</button>
    <div id="evidencePanel" class="hidden">${detail || `<ul class="why-list">${(timeline.events || []).slice(0, 8).map(event => `<li>${esc(describe(event))} · ${esc(fmtDate(event.occurred_at))}</li>`).join('')}</ul>`}</div>
    <h3>${esc(T('recommendedFix'))}</h3>
    <div id="offer"></div>
    ${followUpHtml(clarityState.followUps)}
  </div>`;
}

function buildKnowledgeCardHtml() {
  const articles = clarityState.articles || [];
  const top = articles[0];
  return `<div class="result-card">
    <p class="card-title">${esc('HOW TO')}</p>
    <h3>${esc(top ? top.title : T('unknown'))}</h3>
    <p>${esc(top ? top.body : T('intentHint'))}</p>
    ${followUpHtml(clarityState.followUps)}
  </div>`;
}

function buildMissCardHtml() {
  const finding = T(INTENT_EMPTY[clarityState.intent] || 'intentNone');
  return `<div class="result-card">
    <span class="verdict v-EXPLAIN_ONLY">EXPLAIN ONLY</span>
    <h3>${esc(finding)}</h3>
    <p class="sub">${esc(T('intentHint'))}</p>
    ${followUpHtml(clarityState.followUps)}
  </div>`;
}

function buildCheckingHtml() {
  return `<div class="result-card"><p class="sub">${esc(T('checking'))}</p><p class="sub">${esc(clarityState.turnReply || '')}</p></div>`;
}

function pushClarityMessage(html) {
  clarityState.messages.push({ role: 'clarity', html });
  paintTranscript();
}

function pushUserMessage(text) {
  clarityState.messages.push({ role: 'user', text });
}

function activityHtml() {
  const buckets = [['all', 'all'], ['reloads', 'reloads'], ['packages', 'packages'], ['usage', 'usage'], ['charges', 'charges'], ['refunds', 'refunds']];
  const rows = appState.activity.filter(row => filter === 'all' || row.bucket === filter);
  return `<h1 class="greeting">${esc(T('activity'))}</h1>
    <div class="chip-row">
      ${buckets.map(([value, key]) => `<button type="button" class="chip ${filter === value ? 'on' : ''}" data-act="filter" data-bucket="${value}">${esc(T(key))}</button>`).join('')}
    </div>
    ${rows.length ? rows.map(row => `<button type="button" class="menu-row" data-act="txn" data-id="${esc(row.id)}">
      <span><strong>${esc(row.detail)}</strong><br><span class="sub">${esc(fmtDate(row.at))}</span></span>
      <span>${esc(row.amount_lkr ? lkr(row.amount_lkr) : '')}</span>
    </button>`).join('') : `<p class="sub">${esc(T('empty'))}</p>`}`;
}

function txnHtml() {
  const row = selectedTxn;
  if (!row) return `<p>${esc(T('empty'))}</p>`;
  const receipt = row.bucket === 'refunds' ? appState.receipts[0] : null;
  return `<button type="button" class="btn-ghost" data-act="go" data-view="activity">${esc(T('back'))}</button>
    <h1 class="greeting">${esc(T('details'))}</h1>
    <dl class="kv">
      <dt>${esc(T('amount'))}</dt><dd>${esc(row.amount_lkr ? lkr(row.amount_lkr) : ' - ')}</dd>
      <dt>${esc(T('id'))}</dt><dd class="mono">${esc(row.id)}</dd>
      <dt>${esc(T('time'))}</dt><dd>${esc(fmtDate(row.at))}</dd>
      <dt>${esc(T('category'))}</dt><dd>${esc(T(row.bucket))}</dd>
      <dt>${esc(T('before'))}</dt><dd>${esc(row.balance_before ? lkr(row.balance_before) : ' - ')}</dd>
      <dt>${esc(T('after'))}</dt><dd>${esc(row.balance_after ? lkr(row.balance_after) : ' - ')}</dd>
      <dt>${esc(T('status'))}</dt><dd>${esc(row.status)}</dd>
    </dl>
    <button class="btn-primary" type="button" data-act="ask-txn">${esc(T('askAbout'))}</button>
    ${receipt ? `<button type="button" class="menu-row" data-act="receipt" data-id="${esc(receipt.receipt_id)}">${esc(receipt.receipt_id)}</button>` : ''}`;
}

function moreHtml() {
  const items = [
    ['packages', 'packages'], ['subs', 'subs'], ['safeguards', 'safeguards'],
    ['receipts', 'receipts'], ['cases', 'cases'], ['notifications', 'notifications'],
    ['network', 'network'], ['family', 'family'], ['profile', 'profile']
  ];
  return `<h1 class="greeting">${esc(T('more'))}</h1>` + items.map(([dest, key]) =>
    `<button type="button" class="menu-row" data-act="go" data-view="${dest}">${esc(T(key))}<span>›</span></button>`).join('');
}

function packagesHtml() {
  const order = ['recommended', 'anytime', 'unlimited', 'social', 'work', 'voice', 'combo'];
  const groups = order.map(category => {
    const items = appState.catalogue.filter(item => item.category === category);
    if (!items.length) return '';
    return `<h3>${esc(T('cat_' + category))}</h3>` + items.map(item =>
      `<button type="button" class="menu-row" data-act="pack" data-id="${esc(item.offering_id)}">
        <span><strong>${esc(packLabel(item.name))}</strong><br><span class="sub">${esc(item.apps)}</span></span>
        <span>${esc(lkr(item.price_lkr))}</span>
      </button>`).join('');
  }).join('');
  return `<button type="button" class="btn-ghost" data-act="go" data-view="more">${esc(T('back'))}</button>
    <h1 class="greeting">${esc(T('packages'))}</h1>${groups}`;
}

function packageHtml() {
  const item = selectedPack;
  if (!item) return '';
  const pack = {
    price_lkr: item.price_lkr,
    data_gb: item.data_gb,
    days_left: item.validity_days,
    used_pct: null,
    after_cap_speed: item.after_cap_speed,
    apps: item.apps,
    restrictions: item.after_cap_speed ? `${item.after_cap_speed}` : ' - ',
    renewal: T('renewal'),
    after_expiry: ' - '
  };
  return `<button type="button" class="btn-ghost" data-act="go" data-view="packages">${esc(T('back'))}</button>
    <h1 class="greeting">${esc(packLabel(item.name))}</h1>
    ${packTruth(pack)}
    <button class="btn-primary" type="button" data-act="buy">${esc(T('confirmBuy'))}</button>`;
}

function subsHtml() {
  const rows = appState.subscriptions;
  if (!rows.length) return pageBack('more') + `<h1 class="greeting">${esc(T('subs'))}</h1><p>${esc(T('empty'))}</p>`;
  return pageBack('more') + `<h1 class="greeting">${esc(T('subs'))}</h1>` + rows.map(sub => `
    <section class="soft-card">
      <strong>${esc(sub.name)}</strong>
      <p class="sub">${esc(sub.merchant)} · ${esc(lkr(sub.price_lkr))} · ${esc(sub.renewal)}</p>
      <p class="sub">${sub.consent ? esc(T('consent')) : esc(T('noConsent'))}</p>
      ${sub.charges.length ? `<p class="sub">${esc(sub.charges.map(lkr).join(', '))}</p>` : ''}
      ${sub.active ? `<button class="btn-ghost" type="button" data-act="cancel" data-id="${esc(sub.id)}">${esc(T('cancel'))}</button>` : ''}
    </section>`).join('') + `<button class="btn-primary" type="button" data-act="ask" data-q="qSub">${esc(T('whySub'))}</button>`;
}

function safeHtml() {
  const s = appState.safeguards || {};
  return pageBack('more') + `<h1 class="greeting">${esc(T('safeguards'))}</h1>
    <form id="safeForm" class="card">
      <label class="field">${esc(T('dataExpiry'))}
        <select name="data_on_expiry">
          <option value="stop" ${s.data_on_expiry === 'stop' ? 'selected' : ''}>${esc(T('stopData'))}</option>
          <option value="continue" ${s.data_on_expiry === 'continue' ? 'selected' : ''}>${esc(T('keepData'))}</option>
        </select>
      </label>
      <label class="field">${esc(T('spendCap'))}
        <select name="spend_cap">
          ${['none', '500', '1000', '2000'].map(value => `<option value="${value}" ${s.spend_cap === value ? 'selected' : ''}>${value === 'none' ? esc(T('none')) : 'LKR ' + value}</option>`).join('')}
        </select>
      </label>
      <label class="field">${esc(T('vasConfirm'))}
        <select name="vas_confirm">
          <option value="on" ${s.vas_confirm !== 'off' ? 'selected' : ''}>${esc(T('on'))}</option>
          <option value="off" ${s.vas_confirm === 'off' ? 'selected' : ''}>${esc(T('off'))}</option>
        </select>
      </label>
      <label class="field">${esc(T('usageAlerts'))}
        <select name="usage_alerts">
          <option value="on" ${s.usage_alerts !== 'off' ? 'selected' : ''}>${esc(T('on'))}</option>
          <option value="off" ${s.usage_alerts === 'off' ? 'selected' : ''}>${esc(T('off'))}</option>
        </select>
      </label>
      <label class="field">${esc(T('merchantBlock'))}
        <input name="merchant_block" placeholder="MER-…" value="">
      </label>
      ${appState.blocked_merchants.length ? `<p class="sub">${esc(appState.blocked_merchants.join(', '))}</p>` : ''}
      <button class="btn-primary" type="submit">${esc(T('save'))}</button>
    </form>`;
}

function receiptsHtml() {
  const rows = appState.receipts;
  return pageBack('more') + `<h1 class="greeting">${esc(T('receipts'))}</h1>` +
    (rows.length ? rows.map(row => `<button type="button" class="menu-row" data-act="receipt" data-id="${esc(row.receipt_id)}">
      <span><strong>${esc(row.receipt_id)}</strong><br><span class="sub">${esc(row.summary || '')}</span></span>
      <span>${esc(lkr(row.corrected_lkr))}</span>
    </button>`).join('') : `<p>${esc(T('empty'))}</p>`);
}

function receiptHtml() {
  return pageBack('receipts') + `<section class="card proof-card" id="receiptView"></section>`;
}

function casesHtml() {
  const open = appState.cases.filter(row => row.open);
  const done = appState.cases.filter(row => !row.open);
  const block = (title, rows) => `<h3>${esc(title)}</h3>` + (rows.length ? rows.map(row => `
    <section class="soft-card">
      <strong>${esc(row.case_no)}</strong>
      <p class="sub">${esc(row.state)} ${row.outcome ? '· ' + esc(row.outcome) : ''}</p>
      ${row.headline ? `<p>${esc(row.headline)}</p>` : ''}
    </section>`).join('') : `<p class="sub">${esc(T('empty'))}</p>`);
  return pageBack('more') + `<h1 class="greeting">${esc(T('cases'))}</h1>` + block(T('open'), open) + block(T('resolved'), done);
}

function notesHtml() {
  const rows = appState.notifications;
  return pageBack('more') + `<h1 class="greeting">${esc(T('notifications'))}</h1>` +
    (rows.length ? rows.map(row => `<button type="button" class="menu-row" data-act="note" data-kind="${esc(row.kind)}" data-id="${esc(row.receipt_id || '')}">${esc(row.text)}</button>`).join('')
      : `<p>${esc(T('empty'))}</p>`);
}

function networkHtml() {
  return pageBack('more') + `<h1 class="greeting">${esc(T('network'))}</h1>
    <section class="soft-card"><strong>${esc(appState.network.status === 'clear' ? T('noOutage') : appState.network.text)}</strong></section>
    <div class="btn-row">
      <button class="btn-primary" type="button" data-act="ask" data-q="qSlow">${esc(T('report'))}</button>
    </div>`;
}

function familyHtml() {
  const mine = `<section class="soft-card"><strong>${esc(appState.name)} · ${esc(T('you'))}</strong>
    <p class="sub">${esc(appState.masked)} · ${esc(appState.pack ? packLabel(appState.pack.name) : T('noPack'))}</p></section>`;
  const rows = appState.family.map(row => `<section class="soft-card"><strong>${esc(row.name)}</strong>
    <p class="sub">${esc(row.masked)} · ${esc(row.pack ? packLabel(row.pack) : T('noPack'))}</p>
    <p class="sub">${esc(row.safeguards.join(', ') || T('none'))}</p></section>`).join('');
  return pageBack('more') + `<h1 class="greeting">${esc(T('family'))}</h1>${mine}${rows}
    <form id="familyForm" class="card">
      <label class="field">${esc(T('addNumber'))}<input id="familyNumber" inputmode="tel" required></label>
      <button class="btn-primary" type="submit">${esc(T('save'))}</button>
    </form>`;
}

function profileHtml() {
  return pageBack('more') + `<h1 class="greeting">${esc(T('profile'))}</h1>
    <section class="soft-card"><strong>${esc(appState.name)}</strong><p class="mono">${esc(appState.msisdn)}</p></section>
    <p class="sub">${esc(T('language'))}</p>
    <form id="profileForm" class="card">
      <label class="field">${esc(T('answers'))}
        <select id="answerMode">
          <option value="short" ${answerMode === 'short' ? 'selected' : ''}>${esc(T('short'))}</option>
          <option value="detailed" ${answerMode === 'detailed' ? 'selected' : ''}>${esc(T('detailed'))}</option>
        </select>
      </label>
      <label class="field">${esc(T('notifyLabel'))}
        <select id="profileNotify">
          ${['all', 'important', 'none'].map(value => `<option value="${value}" ${appState.notify === value ? 'selected' : ''}>${esc(T(value === 'all' ? 'notifyAll' : value === 'none' ? 'notifyNone' : 'notifyImportant'))}</option>`).join('')}
        </select>
      </label>
      <label class="field"><span><input id="profileLarge" type="checkbox" ${appState.large_text ? 'checked' : ''}> ${esc(T('largeText'))}</span></label>
      <button class="btn-primary" type="submit">${esc(T('save'))}</button>
    </form>
    <button type="button" class="menu-row" data-act="go" data-view="cases">${esc(T('support'))}</button>
    <button type="button" class="menu-row" data-act="go" data-view="terms">${esc(T('terms'))}</button>
    <button type="button" class="menu-row" data-act="go" data-view="privacy">${esc(T('privacy'))}</button>
    <button type="button" class="btn-ghost" data-act="signout">${esc(T('signOut'))}</button>`;
}

function termsHtml() {
  return pageBack('profile') + `<h1 class="greeting">${esc(T('terms'))}</h1><p>${esc(T('termsBody'))}</p>`;
}
function privacyHtml() {
  return pageBack('profile') + `<h1 class="greeting">${esc(T('privacy'))}</h1><p>${esc(T('privacyBody'))}</p>`;
}
function pageBack(dest) {
  return `<button type="button" class="btn-ghost" data-act="go" data-view="${dest}">${esc(T('back'))}</button>`;
}

function reloadHtml() {
  const amounts = ['100', '200', '500', '1000', '2000'];
  return pageBack('home') + `<h1 class="greeting">${esc(T('reload'))}</h1>
    <div class="quick">${amounts.map(amount => `<button type="button" data-act="reload" data-amount="${amount}">LKR ${amount}</button>`).join('')}</div>`;
}

async function startOtp(msisdn) {
  clearError();
  const started = await api('/v1/auth/otp/request', 'POST', { msisdn });
  pending = { msisdn, challenge: started.challenge_id, sentTo: started.sent_to };
  view = 'otp';
  render();
  try {
    const inbox = await api(`/v1/demo/inbox?msisdn=${encodeURIComponent(msisdn)}`);
    const box = document.getElementById('otp');
    if (box && inbox && inbox.code) {
      box.value = inbox.code;
      box.focus();
    }
  } catch (_error) {
    /* The code stays empty when the delivery port cannot be read. */
  }
}

async function finishOtp(code) {
  clearError();
  const sessionView = await api('/v1/auth/otp/verify', 'POST', {
    challenge_id: pending.challenge, code, channel: 'app'
  });
  signIn(sessionView.token, sessionView.subject);
  appState = await api('/v1/me/app');
  lang = appState.language || 'en';
  view = appState.onboarded ? 'home' : 'onboard';
  render();
}

async function saveOnboard(form) {
  const notify = form.querySelector('#notify').value;
  const large = form.querySelector('#large').checked;
  appState = await api('/v1/me/preferences', 'POST', { language: lang, notify, large_text: large });
  view = 'home';
  render();
}

async function refresh() {
  appState = await api('/v1/me/app');
  render();
}

async function ask(questionKey, wantsHuman, chargeRef, opts) {
  if (!appState) return;
  opts = opts || {};
  if (wantsHuman) {
    await askHuman();
    return;
  }
  const suggested = questionKey ? SUGGESTED.find(item => item.key === questionKey) : null;
  const intentOverride = opts.chatIntent || (suggested && suggested.chatIntent) || null;
  const typed = questionKey
    ? T(questionKey)
    : (clarityState.question || (intentOverride ? String(intentOverride) : ''));
  if (!typed) return;
  view = 'clarity';
  if (window.ClarityChat) {
    ClarityChat.pushUser(typed);
  } else {
    pushUserMessage(typed);
  }
  clarityState.question = typed;
  clarityState.chargeRef = chargeRef || null;
  clarityState.decision = null;
  clarityState.timeline = null;
  clarityState.caseId = null;
  clarityState.planId = null;
  clarityState.receipt = null;
  clarityState.receiptDoc = null;
  clarityState.articles = null;
  clarityState.mode = 'checking';
  clarityState.turnReply = null;
  clarityState.followUps = [];
  if (!clarityState.contextProduct) {
    const sub = ((appState && appState.subscriptions) || []).find(item => item.active && !item.consent);
    if (sub) clarityState.contextProduct = sub.name || sub.product || sub.merchant || null;
  }
  paintChrome();
  if (window.ClarityChat) {
    ClarityChat.setThinking(T('checking'));
  } else {
    render();
    pushClarityMessage(buildCheckingHtml());
  }

  let clientIntent = intentForQuestion(questionKey, typed);
  let route = 'account';
  const priorFacts = window.ClarityChat ? ClarityChat.contextFacts() : {};
  try {
    const turned = await api('/v1/conversation/turn', 'POST', {
      text: typed,
      language: lang,
      intent: intentOverride,
      facts: priorFacts,
      snapshot: {
        pack: appState.pack || {},
        subscriptions: appState.subscriptions || [],
        activity: appState.activity || []
      }
    });
    const turn = turned.turn || {};
    const intake = turn.intake || {};
    clarityState.turnReply = turn.reply || '';
    clarityState.chatIntent = intake.intent || intentOverride;
    clarityState.followUps = turn.follow_ups || [];
    clientIntent = turn.client_intent || intake.client_intent || clientIntent;
    route = turn.route || intake.route || route;
    if (turn.articles) clarityState.articles = turn.articles;
    clarityState.intent = clientIntent;
    if (intake.slots && intake.slots.product) clarityState.contextProduct = intake.slots.product;
    if (intake.slots && intake.slots.amount_lkr) clarityState.contextAmount = intake.slots.amount_lkr;
  } catch (_error) {
    clarityState.intent = clientIntent;
  }

  const can = accountIntents();

  if (route === 'knowledge' || clientIntent === 'knowledge') {
    if (!clarityState.articles) {
      try {
        const routed = await api('/v1/clarity/route', 'POST', { question: typed, language: lang });
        clarityState.articles = routed.articles || [];
      } catch (_e) {
        clarityState.articles = [];
      }
    }
    clarityState.mode = 'knowledge';
    clarityState.intent = 'knowledge';
    if (window.ClarityChat) {
      ClarityChat.finishWithCard('knowledge');
    } else {
      clarityState.messages.pop();
      pushClarityMessage(buildKnowledgeCardHtml());
    }
    return;
  }

  if (route === 'handoff' || clientIntent === 'human') {
    await askHuman();
    return;
  }

  if (!chargeRef && clientIntent !== 'knowledge' && !can[clientIntent]) {
    clarityState.mode = 'miss';
    if (window.ClarityChat) {
      ClarityChat.finishWithCard('miss');
    } else {
      clarityState.messages.pop();
      pushClarityMessage(buildMissCardHtml());
    }
    return;
  }

  try {
    if (window.ClarityChat) {
      ClarityChat.setThinking(T('lookingActivity'));
      ClarityChat.setProgress(0);
    }
    await evaluateCase(clientIntent, chargeRef || chargeForIntent(clientIntent), false, true);
    const d = clarityState.decision || {};
    if (d.product) clarityState.contextProduct = d.product;
    if (d.amount_lkr) clarityState.contextAmount = d.amount_lkr;
    clarityState.mode = d.outcome === 'HANDOFF' ? 'human' : 'result';
    if (window.ClarityChat) {
      ClarityChat.finishWithCard(ClarityChat.pickResultKind(clarityState));
    } else {
      clarityState.messages.pop();
      pushClarityMessage(buildResultCardHtml());
      fillOffer(clarityState.decision || {});
    }
  } catch (error) {
    showError(error);
  }
}

async function askHuman() {
  const q = T('human');
  if (!clarityState.messages.length || clarityState.messages[clarityState.messages.length - 1].text !== q) {
    if (window.ClarityChat) ClarityChat.pushUser(q);
    else pushUserMessage(q);
  }
  clarityState.question = q;
  clarityState.intent = 'human';
  clarityState.chatIntent = 'HANDOFF';
  clarityState.chargeRef = null;
  clarityState.decision = null;
  clarityState.receipt = null;
  clarityState.receiptDoc = null;
  clarityState.mode = 'checking';
  clarityState.followUps = [];
  view = 'clarity';
  paintChrome();
  if (window.ClarityChat) ClarityChat.setThinking(T('checking'));
  else {
    render();
    pushClarityMessage(buildCheckingHtml());
  }
  try {
    await evaluateCase('human', null, true, true);
    clarityState.mode = 'human';
    if (window.ClarityChat) ClarityChat.finishWithCard('handoff');
    else {
      clarityState.messages.pop();
      pushClarityMessage(buildResultCardHtml());
      fillOffer(clarityState.decision || {});
    }
  } catch (error) {
    showError(error);
  }
}

async function evaluateCase(intent, chargeRef, wantsHuman, withProgress) {
  if (withProgress && window.ClarityChat) ClarityChat.setProgress(1);
  const opened = await api('/v1/cases', 'POST', {
    msisdn: appState.msisdn,
    channel: 'app',
    language: lang,
    charge_ref: chargeRef || null,
    customer_requested_human: !!wantsHuman
  });
  clarityState.caseId = opened.case_id;
  clarityState.chargeRef = chargeRef || null;
  if (withProgress && window.ClarityChat) ClarityChat.setProgress(2);
  const [decision, timeline] = await Promise.all([
    api(`/v1/cases/${opened.case_id}/evaluate?human=${wantsHuman ? 'true' : 'false'}`, 'POST'),
    api(`/v1/cases/${opened.case_id}/timeline`)
  ]);
  if (withProgress && window.ClarityChat) ClarityChat.setProgress(3);
  clarityState.decision = decision;
  clarityState.timeline = timeline;
  return decision;
}

function renderAnswer() {
  paintTranscript();
}

function fillOffer(d) {
  const offer = document.getElementById('offer');
  if (!offer) return;
  if (clarityState.mode === 'human' || d.outcome === 'HANDOFF') {
    offer.innerHTML = `<p>${esc(T('humanFinding'))}</p>`;
    return;
  }
  if (d.outcome === 'EXPLAIN_ONLY') {
    offer.innerHTML = `<div class="btn-row"><button class="btn-primary" id="go" type="button">${esc(T('getReceipt'))}</button></div>`;
    document.getElementById('go').onclick = () => explainReceipt();
    return;
  }
  if (d.outcome === 'STAFF_APPROVAL') {
    offer.innerHTML = `<div class="btn-row"><button class="btn-primary" id="go" type="button">${esc(T('confirm'))}</button></div>`;
    document.getElementById('go').onclick = async () => {
      await propose();
      appState = await api('/v1/me/app');
      offer.innerHTML = `<p>${esc(T('sent'))}</p>`;
    };
    return;
  }
  const verb = d.outcome === 'AUTO_FIX' ? T('apply') : T('confirm');
  offer.innerHTML = `<h3>${esc(T('canDo'))}</h3>
    <ul class="why-list">${(d.allowed_actions || []).map(action => `<li>${esc(actionText(action, d))}</li>`).join('')}</ul>
    <div class="btn-row"><button class="btn-primary" id="go" type="button">${esc(verb)}</button></div>`;
  document.getElementById('go').onclick = () => confirmFix(d.outcome);
}

function actionText(action, d) {
  const map = {
    REFUND: T('actRefund').replace('{amount}', d.amount_lkr || ''),
    DEACTIVATE_VAS: T('actOff'),
    BLOCK_MERCHANT_UNTIL_OPTIN: T('actBlock'),
    SET_SPEND_CAP: T('actCap'),
    ENABLE_DATA_STOP: T('actStop'),
    ENABLE_FUP_ALERTS: T('actAlert')
  };
  return map[action] || action;
}

async function propose() {
  const plan = await api(`/v1/cases/${clarityState.caseId}/proposals`, 'POST', { created_by: 'channel:web' });
  clarityState.planId = plan.plan_id;
  return plan;
}

async function proposeAndSend() {
  try {
    await propose();
    clarityState.mode = 'human';
    clarityState.followUps = [{ id: 'support', i18n_key: 'fuSupport', intent: 'HANDOFF' }];
    appState = await api('/v1/me/app');
    if (window.ClarityChat) {
      ClarityChat.pushAi('handoff');
      ClarityChat.remountBody();
      ClarityChat.persistCurrentThread();
    } else {
      const offer = document.getElementById('offer');
      if (offer) offer.innerHTML = `<p>${esc(T('sent'))}</p>`;
    }
  } catch (error) {
    showError(error);
  }
}

async function confirmFix(outcome) {
  const button = document.getElementById('go');
  if (button) { button.disabled = true; button.textContent = T('working'); }
  try {
    await propose();
    const path = outcome === 'AUTO_FIX' ? 'auto-fix' : 'confirm';
    const done = await api(`/v1/cases/${clarityState.caseId}/${path}`, 'POST', { plan_id: clarityState.planId });
    const verified = await api(`/v1/receipts/${done.receipt_id}/verify`, 'POST');
    const full = await api(`/v1/receipts/${done.receipt_id}`);
    clarityState.receiptDoc = full;
    clarityState.receiptCheck = verified;
    clarityState.mode = 'resolved';
    clarityState.followUps = [
      { id: 'prevent', i18n_key: 'fuPrevent', intent: 'PREVENT_CHARGES' },
      { id: 'support', i18n_key: 'fuSupport', intent: 'HANDOFF' }
    ];
    appState = await api('/v1/me/app');
    if (window.ClarityChat) {
      ClarityChat.showSuccessAndReceipt();
    } else {
      const offer = document.getElementById('offer');
      if (offer) offer.innerHTML = `<p>${esc(T('done'))}</p>`;
      pushClarityMessage(`<div class="result-card resolved">
        <p class="card-title">✓ ${esc(T('resolvedTitle'))}</p>
        <p>${esc(T('done'))}</p>
        <button type="button" class="btn-primary" data-act="receipt" data-id="${esc(done.receipt_id)}">${esc(T('viewReceipt'))}</button>
        ${followUpHtml(clarityState.followUps)}
      </div>`);
      paintReceipt(full, verified);
    }
  } catch (error) {
    showError(error);
    if (button) { button.disabled = false; button.textContent = T('tryAgain'); }
  }
}

async function explainReceipt() {
  const button = document.getElementById('go');
  if (button) { button.disabled = true; button.textContent = T('working'); }
  try {
    const verified = await api(`/v1/cases/${clarityState.caseId}/receipt`, 'POST');
    const full = await api(`/v1/receipts/${verified.receipt_id}`);
    appState = await api('/v1/me/app');
    clarityState.receiptDoc = full;
    clarityState.receiptCheck = verified;
    if (window.ClarityChat && view === 'clarity') {
      ClarityChat.pushAi('receipt');
      ClarityChat.remountBody();
      ClarityChat.persistCurrentThread();
    } else {
      paintReceipt(full, verified);
    }
  } catch (error) {
    showError(error);
    if (button) button.disabled = false;
  }
}

function paintReceipt(full, verified) {
  const host = document.getElementById('receipt') || document.getElementById('receiptView');
  if (!host) return;
  const payload = full.payload || {};
  const happened = payload.what_happened ? payload.what_happened.summary : '';
  const found = payload.what_happened && payload.decision
    ? `${payload.what_happened.cause_rule} · ${payload.decision.outcome}` : '';
  const actions = (payload.actions || []).map(action => `<li>${esc(String(action.type).replace(/_/g, ' ').toLowerCase())}${
    action.amount_lkr ? ' · ' + esc(lkr(action.amount_lkr)) : ''}${
    action.before && action.before.balance_lkr ? ` - ${esc(action.before.balance_lkr)} → ${esc(action.after.balance_lkr)}` : ''}</li>`).join('');
  const guard = payload.safeguard ? String(payload.safeguard.type || payload.safeguard.status) : (verified && verified.safeguard) || '';
  const recurrence = payload.recurrence_test ? payload.recurrence_test.result : (verified && verified.recurrence_test) || '';
  host.innerHTML = `<div class="receipt-head"><div><h2>Trust Receipt</h2><div class="receipt-id">${esc(verified.receipt_id)}</div></div>
      <span class="stamp ${verified.valid ? 'ok' : 'bad'}">${esc(verified.status)}</span></div>
    <h3>${esc(T('happened'))}</h3><p>${esc(happened)}</p>
    <h3>${esc(T('find'))}</h3><p>${esc(found)}</p>
    <h3>${esc(T('corrected'))}</h3>${actions ? `<ul class="why-list">${actions}</ul>` : `<p>${esc(lkr(verified.corrected_lkr))}</p>`}
    <h3>${esc(T('protects'))}</h3><p>${esc(guard || ' - ')}${recurrence ? ' · ' + esc(recurrence) : ''}</p>
    <dl class="kv">
      <dt>${esc(T('returned'))}</dt><dd>${esc(lkr(verified.corrected_lkr))}</dd>
      <dt>${esc(T('signed'))}</dt><dd class="mono">${esc(verified.key_id || '')}</dd>
      <dt>${esc(T('chain'))}</dt><dd>${verified.chain_ok ? esc(T('intact')) : esc(T('notVerified'))}</dd>
    </dl>
    <div class="qr"><img src="/v1/receipts/${encodeURIComponent(verified.receipt_id)}/qr.svg" alt="QR">
      <div class="hint"><a href="/v/${encodeURIComponent(verified.receipt_id)}">${esc(verified.receipt_id)}</a></div>
    </div>`;
  host.classList.remove('hidden');
}

function describe(event) {
  const attrs = event.attributes || {};
  const money = event.amount_lkr ? ` LKR ${event.amount_lkr}` : '';
  const label = String(event.event_type).replace(/_/g, ' ');
  if (attrs.merchant_name) return `${label}${money} - ${attrs.merchant_name}`;
  if (attrs.product) return `${label}${money} - ${attrs.product}`;
  return `${label}${money}`;
}

function listen() {
  const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Speech) {
    showError(new Error(T('micMissing')));
    return;
  }
  if (recognition) recognition.stop();
  recognition = new Speech();
  recognition.lang = lang === 'si' ? 'si-LK' : lang === 'ta' ? 'ta-LK' : 'en-LK';
  recognition.onresult = (event) => {
    const said = event.results[0][0].transcript;
    document.getElementById('composerInput').value = said;
  };
  recognition.start();
  document.getElementById('mic').textContent = T('listening');
}

async function openReceipt(id) {
  const full = await api(`/v1/receipts/${encodeURIComponent(id)}`);
  const verified = await api(`/v1/receipts/${encodeURIComponent(id)}/verify`, 'POST');
  clarityState.receiptDoc = full;
  clarityState.receiptCheck = verified;
  go('receipt');
}

async function setLang(next) {
  const notifyEl = document.getElementById('notify');
  if (notifyEl) onboard.notify = notifyEl.value;
  const largeEl = document.getElementById('large');
  if (largeEl) onboard.large = largeEl.checked;
  lang = next;
  if (signedIn() && appState && appState.onboarded) {
    appState = await api('/v1/me/preferences', 'POST', {
      language: lang,
      notify: appState.notify,
      large_text: appState.large_text
    });
  }
  render();
}

document.addEventListener('click', async (event) => {
  if (window.ClarityChat && view === 'clarity' && ClarityChat.onClick(event)) {
    event.preventDefault();
    return;
  }
  const langBtn = event.target.closest('[data-lang]');
  if (langBtn) {
    event.preventDefault();
    await setLang(langBtn.dataset.lang);
    return;
  }
  const tab = event.target.closest('#tabbar [data-go]');
  if (tab) { go(tab.dataset.go); return; }
  const act = event.target.closest('[data-act]');
  if (!act) return;
  const name = act.dataset.act;
  try {
    clearError();
    if (name === 'back-login') { pending = { msisdn: null, challenge: null, sentTo: '' }; go('login'); }
    if (name === 'fill-number') {
      const field = document.getElementById('msisdn');
      if (field) {
        field.value = act.dataset.number;
        field.focus();
      }
      return;
    }
    if (name === 'go') go(act.dataset.view);
    if (name === 'ask') await ask(act.dataset.q, false, null, { chatIntent: act.dataset.intent || null });
    if (name === 'ask-human') await ask(null, true, null);
    if (name === 'follow') {
      const key = act.dataset.key;
      const intent = act.dataset.intent;
      if (intent === 'HANDOFF') {
        await ask(null, true, null);
      } else if (key && T(key) !== key) {
        clarityState.question = T(key);
        await ask(null, false, null, { chatIntent: intent || null });
      } else {
        await ask(null, false, null, { chatIntent: intent || null });
      }
    }
    if (name === 'toggle-more') {
      clarityState.showMore = !clarityState.showMore;
      paintSuggestionChips();
    }
    if (name === 'toggle-evidence') {
      const panel = document.getElementById('evidencePanel');
      if (panel) panel.classList.toggle('hidden');
    }
    if (name === 'ask-txn') {
      if (selectedTxn) clarityState.question = selectedTxn.detail || T('askAbout');
      await ask(null, false, selectedTxn && selectedTxn.id);
    }
    if (name === 'filter') { filter = act.dataset.bucket; render(); }
    if (name === 'window') { usageWindow = act.dataset.window; render(); }
    if (name === 'txn') {
      selectedTxn = appState.activity.find(row => row.id === act.dataset.id);
      go('txn');
    }
    if (name === 'pack') {
      selectedPack = appState.catalogue.find(item => item.offering_id === act.dataset.id);
      go('package');
    }
    if (name === 'buy') {
      appState = await api(`/v1/me/packages/${encodeURIComponent(selectedPack.offering_id)}/purchase`, 'POST');
      go('home');
    }
    if (name === 'reload') {
      appState = await api('/v1/me/reload', 'POST', { amount_lkr: act.dataset.amount });
      go('home');
    }
    if (name === 'cancel') {
      appState = await api(`/v1/me/subscriptions/${encodeURIComponent(act.dataset.id)}/cancel`, 'POST');
      render();
    }
    if (name === 'receipt') await openReceipt(act.dataset.id);
    if (name === 'note') {
      if (act.dataset.kind === 'receipt' && act.dataset.id) await openReceipt(act.dataset.id);
      else if (act.dataset.kind === 'case') go('cases');
      else await ask('qBalance', false, null);
    }
    if (name === 'signout') {
      signOut();
      appState = null;
      view = 'login';
      render();
    }
  } catch (error) {
    showError(error);
  }
});

document.addEventListener('submit', async (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;
  if (!['loginForm', 'otpForm', 'onboardForm', 'safeForm', 'familyForm', 'profileForm', 'composerForm'].includes(form.id)) return;
  event.preventDefault();
  try {
    clearError();
    if (form.id === 'loginForm') await startOtp(document.getElementById('msisdn').value.trim());
    if (form.id === 'otpForm') await finishOtp(document.getElementById('otp').value.trim());
    if (form.id === 'onboardForm') await saveOnboard(form);
    if (form.id === 'safeForm') {
      const data = new FormData(form);
      for (const kind of ['data_on_expiry', 'spend_cap', 'vas_confirm', 'usage_alerts']) {
        appState = await api('/v1/me/safeguards', 'POST', { kind, value: String(data.get(kind) || '') });
      }
      const merchant = String(data.get('merchant_block') || '').trim();
      if (merchant) appState = await api('/v1/me/safeguards', 'POST', { kind: 'merchant_block', value: merchant });
      render();
    }
    if (form.id === 'familyForm') {
      appState = await api('/v1/me/family', 'POST', { msisdn: document.getElementById('familyNumber').value.trim() });
      render();
    }
    if (form.id === 'profileForm') {
      answerMode = document.getElementById('answerMode').value;
      appState = await api('/v1/me/preferences', 'POST', {
        language: lang,
        notify: document.getElementById('profileNotify').value,
        large_text: document.getElementById('profileLarge').checked
      });
      render();
    }
    if (form.id === 'composerForm') {
      const text = document.getElementById('composerInput').value.trim();
      const human = /human|person|agent|කෙනෙකු|நபர்/.test(text.toLowerCase());
      document.getElementById('composerInput').value = '';
      clarityState.question = text;
      await ask(null, human, null);
    }
  } catch (error) {
    showError(error);
  }
});

document.getElementById('mic').onclick = () => listen();

document.getElementById('composerInput').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    document.getElementById('composerForm').requestSubmit();
  }
});

if (window.ClarityChat) {
  ClarityChat.init({
    T,
    esc,
    api,
    getLang: () => lang,
    setLang,
    getState: () => clarityState,
    getApp: () => appState,
    go,
    ask,
    confirmFix,
    proposeAndSend,
    explainReceipt,
    openReceipt,
    SUGGESTED,
    INTENT_EMPTY,
    fmtDate,
    describe,
    packLabel
  });
}

window.addEventListener('popstate', () => {
  const next = (location.hash || '#login').slice(1);
  if (next) view = next;
  render();
});

render();

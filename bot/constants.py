"""Constant messages for the bot."""

# ==================== GREETING & INTRO ====================

# ==================== STAGE 1: INITIAL REGISTRATION ====================

GREETING_MESSAGE = (
    "👋 Assalomu alaykum!\n\n"
    "Rahimov Matematika Olimpiadasi rasmiy botiga xush kelibsiz 😊\n\n"
    "Yuqoridagi videoni siz uchun tayyorladik, diqqat bilan tomosha qiling.\n\n"
    "Botdan foydalanish uchun esa, ro'yxatdan o'tishingiz lozim ✅\n\n"
    "📝 Ismingizni kiriting:"
)

# Greeting shown before user clicks inline Web App button
REG_GREETING_MESSAGE = (
    "Rahimov Matematika Olimpiadasida qatnashishga qaror qilganingizdan xursandmiz 🙌\n\n"
    "Quyidagi tugmani bosib ro'yxatdan o'ting:"
)
REG_BUTTON_LABEL = "📝 Ro'yxatdan o'tish"

# After Web App registration (POST submit): success and follow-up message + button labels
REG_SUCCESS_MESSAGE = (
    "✅ Muvaffaqiyatli ro'yxatdan o'tdingiz!\n\n"
    "Ma'lumotlaringiz saqlandi. Endi testda qatnashishingiz va 100$ mukofotli konkursda ishtirok etishingiz mumkin."
)
REG_AFTER_MESSAGE = (
    "🎯 Testda qatnashing va 100$ gacha mukofot olish imkoniyatiga ega bo'ling!\n\n"
    "Quyidagi tugmalardan birini tanlang:"
)
REG_BTN_MAIN_MENU = "🏠 Boshqa menyu"
REG_BTN_PARTICIPATE_CONTEST = "🏆 Konkursda qatnashish"
REG_BTN_PARTICIPATE_TEST = "📝 Testda qatnashish"

STEP_INITIAL_PHONE = (
    "2. Telefon raqamingiz:"
)

STEP_PHONE_OWNER = (
    "3. Ushbu telefon raqam:"
)

SUCCESS_INITIAL_REG = (
    "Botdan muvaffaqiyatli ro'yxatdan o'tdingiz, {full_name} ✅"
)

PROMO_TEXT = (
    "Toshkentdagi xususiy maktablardan biri — Rahimov School xususiy maktabida mutlaqo bepul o'qish imkoniyatiga nima deysiz?\n\n"
    "Viloyatdan bo'lsangiz, yeb-ichish va yotoqxonangizgacha ta'minlab beramiz 🔥\n\n"
    "Maktabimiz haqiqiy iqtidorlarni qidirmoqda 🌟\n\n"
    "\"Rahimov Matematika Olimpiadasi\"da qatnashib, 12 ta grant sohibidan biri bo'ling.\n\n"
    "Olimpiadada qatnashmoqchimisiz?"
)

OLYMPIAD_INTRO = (
    "Olimpiadada ishtirok etish uchun oldinda sizni 17 qadamlik ro'yxatdan o'tish jarayoni kutib turibdi 🤭\n\n"
    "Bizga nomzodning quyidagi ma'lumotlari kerak bo'ladi:\n\n"
    "1. Nomzod haqida:\n"
    "• Ism\n"
    "• Familiya\n"
    "• Tug'ilgan sana\n"
    "• Metrika raqami\n"
    "• Viloyat\n"
    "• Tuman/shahar\n"
    "• Maktab\n"
    "• Sinf\n"
    "• O'qish tili\n"
    "• Foto\n\n"
    "2. Vasiyingiz haqida\n"
    "3. Ustozingiz haqida\n\n"
    "Ko'p kuttirmasdan, boshlaylik unda😉\n\n"
    "1-qadam: Ismingizni kiriting:"
)

OLYMPIAD_DECLINED = (
    "Botimizga xush kelibsiz, olimpiada jarayonlarini ushbu kanalda kuzatib borishingiz mumkin:\n\n"
    "@rs_olimpiada / @RahimovSchool"
)


# ==================== STUDENT REGISTRATION STEPS (STAGE 2) ====================

STEP_1_ASK_NAME = (
    "1-qadam: Ismingizni kiriting:"
)

STEP_2_ASK_SURNAME = (
    "Rahmat, {first_name} 🙌\n\n"
    "Navbat 2-qadamga: Familiyangizni kiriting:"
)

STEP_3_ASK_DOB = (
    "Familiyangiz ham muvaffaqiyatli saqlandi ✅\n\n"
    "Endi, 3-qadam: Qaysi sanada tug'ilgansiz? 😊\n\n"
    "Faqat bitta iltimos, tug'ilgan sanangizni DD-MM-YYYY formatida kiriting, ya'ni: 15-05-2010"
)

STEP_4_ASK_METRIKA = (
    "Tug'ilgan sanangiz chiroyli sana ekan-a? 🙂\n\n"
    "✅ Muvaffaqiyatli saqlandi: {date_str}\n\n"
    "Endigi navbat, 4-qadam: Tug'ilganlik haqida guvohnomangizning raqamiga:"
)

STEP_5_ASK_REGION = (
    "✅ Metrika raqamingizni saqladik: <b>{document_number}</b>\n\n"
    "Bizda 5-qadam: Viloyatingizni belgilang:"
)

STEP_6_ASK_DISTRICT = (
    "{region_label}danmisiz? 🙃 Ajoyib-ku 🔥\n\n"
    "6-qadamga ham yetib keldik: Qaysi tuman/shaharda istiqomat qilasiz?"
)

STEP_7_ASK_SCHOOL = (
    "{district} saqlandi ⭐️\n\n"
    "7-qadamga yetib keldik: Qaysi maktabda o'qiysiz?\n\n"
    "Javobingiz quyidagi formatda yuborsangiz:" 
    "3-maktab/ixtisoslashtirilgan maktab"
)

STEP_8_ASK_GRADE = (
    "8-qadam: {school_name}da nechanchi sinfsiz? 🙂"
)

STEP_9_ASK_PHOTO = (
    "✅ Sinifingiz saqlandi:\n\n"
    "Endi, 9-qadam: Rasmingizni yuboring 🖼"
)

# ==================== ACHIEVEMENTS ====================

STEP_10_ASK_ACHIEVEMENTS = (
    "Rasmga gap yo'q 🔥\n\n"
    "10-qadamimiz biroz uzunroq:\n\n"
    "Avvalgi yutuqlaringiz haqida nima deyolasiz?\n\n"
    "(Yutuqlaringiz bo'lmasa, \"O'tkazib yuborish\" tugmasini bosishingiz mumkin)"
)

# ==================== GUARDIAN INFO ====================

STEP_11_ASK_GUARDIAN_NAME = (
    "✅ 11-qadamga keldik:\n\n"
    "Endi vasiyingiz haqida ma'lumotlar so'raymiz 🙂\n\n"
    "Vasiyingiz to'liq ismlarini yozing:"
)

STEP_12_ASK_RELATIONSHIP = (
    "✅ 12-qadam: Kiritilgan vasiy sizga kim? 🙃"
)

STEP_13_ASK_GUARDIAN_PHONE = (
    "13-qadam: {relation_text}ning telefon raqamini kirita olasizmi? 👇"
)

# ==================== TEACHER INFO ====================

STEP_14_ASK_TEACHER_NAME = (
    "✅ 14-qadamga keldik:\n\n"
    "Endi ustozingiz haqida ma'lumotlar so'raymiz 🙂\n\n"
    "Ustozingiz to'liq ismlarini yozing:"
)

STEP_15_ASK_TEACHER_PHONE = (
    "📞 15-qadam: Telefon raqamlarini yozsangiz"
)

# ==================== SOURCE & CONFIRMATION ====================

STEP_16_ASK_SOURCE = (
    "🙌 Oxiridan 1 ta oldingi qadamdamiz — 16-qadam:\n\n"
    "Olimpiadamiz haqida qayerdan eshitdingiz? 🙃"
)

STEP_17_CONFIRMATION_HEADER = (
    "🥳 Nihoyat, eng so'nggi qadam (17-qadam):\n\n"
    "📝 Ushbu ma'lumotlarni tasdiqlaysizmi? 👇\n\n"
)

SUCCESS_MESSAGE = (
    "✅ Rasman! Siz Rahimov Matematika Olimpiadasi ishtirokchisisiz! 🔥\n\n"
    "Olimpiada jarayonlarini ushbu kanalda kuzatib borishingiz mumkin:\n"
    "@rs_olimpiada / @RahimovSchool"
)

OTHER_GRADE_SUCCESS_MESSAGE = (
    "Olimpiadamiz 5-6-7-8-sinflar uchun o'tkazilmoqda 🙂\n\n"
    "Boshqa sinflar uchun grantlardan boxabar bo'lib turish uchun "
    "kanallarimizni kuzatib boring 👇\n\n"
    "@RahimovSchool / @RS_Olimpiada"
)

PROMO_MESSAGE = (
    "👋 Assalomu alaykum!\n\n"
    "Toshkentdagi xususiy maktablardan biri — <a href=\"http://t.me/rahimovschool\">Rahimov School</a> xususiy maktabida mutlaqo bepul o'qishni istaysizmi?\n\n"
    "Viloyatdan bo'lsangiz, yeb-ichish va yotoqxonangizgacha ta'minlab berisharkan 🔥\n\n"
    "\"Rahimov Matematika Olimpiadasi\"da qatnashib, 12 ta grant sohibidan biri bo'ling.\n\n"
    "Maktab iqtidorlarni qidirmoqda 🔥\n\n"
    "Olimpiada haqida batafsil:\n"
    "https://telegra.ph/Rahimov-Matematika-Olimpiadasi-02-05\n\n"
    "Siz ham quyidagi havola orqali ro'yxatdan o'tishingiz mumkin:\n"
    "{referral_link}"
)

# 30-second delayed message sent after web app registration
PROMO_AFTER_REG_TEXT = (
    "Rahimov Matematika Olimpiadasini qolganlarga ham yetib borishida yordamlashing "
    "va maxsus mukofotlarga ega bo'ling 🎁\n\n"
    "😎 Sizni <b>ajoyib sovg'alar va maxsus mukofotlar</b> kutmoqda!\n\n"
    "✅ Quyidagi tugmani bosib maxsus konkursda qatnashing va siz uchun nima sovg'alar "
    "tayyorlaganimizni bilib oling."
)

# Contest promo message with referral link (sent with logo photo)
CONTEST_PROMO_MESSAGE = (
    "Aloqadamisiz? Sizga maxsus xabar bor!\n\n"
    "Rahimov Matematika Olimpiadasini eng ko'p tarqatganlar uchun mukofotlar o'ynayapmiz:\n\n"
    "<b>1-o'rin</b> — 100$\n"
    "<b>2-o'rin</b> — 500 000 so'm\n"
    "<b>3-o'rin</b> — 250 000 so'm\n"
    "4-o'rin — 100 000 so'm\n"
    "5-10-o'rinlar — Telegram premium obunasiz\n"
    "11-20-o'rinlar — Parallel Muhit obunasi\n"
    "21-25-o'rinlar — \"Zehn tuzoqlari\" kitobi\n\n"
    "25 ta o'ringa kira olmaganlar uchun <b>EKSKLYUZIV YANGILIK— 5 nafardan ko'p do'st taklif qilgan</b> "
    "har bir ishtirokchi uchun <b>50 000 so'm</b> yutish imkoniyati mavjud.\n\n"
    "Shoshiling sizlar uchun bunday imkoniyat qayta bo'lmasligi mumkin:\n\n"
    "{referral_link}"
)

# Reply to contest promo message
CONTEST_PROMO_REPLY = (
    "👆 Yuqoridagi sizning <b>referal havolangiz.</b> "
    "Uni ko\u02bcproq tanishlaringizga ulashing va g'olib bo'ling. Omad!"
)

# Promo message for "other" grade users (sent after 30 sec, directly with referral link)
OTHER_GRADE_PROMO_MESSAGE = (
    "Kanalga ulanib oldingizmi?\n\n"
    "Olimpiadada qatnasha olmas ekanmiz deb xafa bo'lmang. "
    "Bizda siz uchun boshqa taklif bor 🤩\n\n"
    "Rahimov Matematika Olimpiadasini eng ko'p tarqatganlar uchun mukofotlar o'ynayapmiz:\n\n"
    "<b>1-o'rin</b> — 100$\n"
    "<b>2-o'rin</b> — 500 000 so'm\n"
    "<b>3-o'rin</b> — 250 000 so'm\n"
    "4-o'rin — 100 000 so'm\n"
    "5-10-o'rinlar — Telegram premium obunasiz\n"
    "11-20-o'rinlar — Parallel Muhit obunasi\n"
    "21-25-o'rinlar — \"Zehn tuzoqlari\" kitobi\n\n"
    "25 ta o'ringa kira olmaganlar uchun <b>EKSKLYUZIV YANGILIK— 5 nafardan ko'p do'st taklif qilgan</b> "
    "har bir ishtirokchi uchun <b>50 000 so'm</b> yutish imkoniyati mavjud.\n\n"
    "Shoshiling sizlar uchun bunday imkoniyat qayta bo'lmasligi mumkin:\n\n"
    "{referral_link}"
)

REFERRAL_ONLY_PROMO_TEXT = (
    "Iste'dodli o'quvchilarga yordam berishga qaror qilganingizdan xursandmiz! 😊\n\n"
    "<b>Olimpiadaga 5-8-sinflarga tarqating va rasmdagi sovg'a sohibiga aylaning 🎁:</b>\n\n"
    "🥇 1-o'rin —- <a href=\"https://t.me/rs_olimpiada/32\">sovg'alarni bu yerdan ko'ring</a>\n"
    "🥈 2-o'rin — <a href=\"https://t.me/rs_olimpiada/31\">sovg'alarni bu yerdan ko'ring</a>\n"
    "🥉 3-o'rin — <a href=\"https://t.me/rs_olimpiada/30\">sovg'alarni bu yerdan ko'ring</a>\n"
    "🎖 4-20-o'rin — <a href=\"https://t.me/rs_olimpiada/29\">sovg'alarni bu yerdan ko'ring</a>\n\n"
    "📌 Har bir havolangiz orqali ro'yxatdan o'tgan do'stingiz uchun 5 ball olasiz\n\n"
    "Rozi bo'lsangiz, \"Ha 🔥\" tugmasini bosing. Biz do'stlaringizga yuborishingiz kerak bo'lgan tayyor xabarni yuboramiz ⚡"
)

# ==================== ERROR MESSAGES ====================

ERROR_NAME_LENGTH = "❌ Iltimos, to'g'ri ism kiriting (kamida 2 ta belgi):"
ERROR_SURNAME_LENGTH = "❌ Iltimos, to'g'ri familiya kiriting (kamida 2 ta belgi):"
ERROR_DATE_FORMAT = (
    "❌ Iltimos, to'g'ri formatda kiriting (DD-MM-YYYY):\n"
    "Masalan: 15-05-2010"
)
ERROR_INVALID_PHOTO = "❌ Iltimos, rasm yuboring (foto yoki rasm fayl):"
ERROR_INVALID_FILE = "❌ Iltimos, fayl yoki rasm yuboring:"
ERROR_INVALID_AGE = "❌ Iltimos, to'g'ri yosh kiriting (18-120):"
ERROR_INVALID_PHONE_UZB = (
    "❌ Iltimos, to'g'ri O'zbekiston telefon raqamini kiriting:\n"
    "Masalan: +998901234567 yoki 901234567"
)
ERROR_USE_BUTTONS = "❌ Iltimos, tugmalardan foydalaning."

# ==================== MISC ====================

ALREADY_REGISTERED = (
    "Assalomu alaykum, {first_name}!\n\n"
    "Siz allaqachon ro'yxatdan o'tgansiz. Quyidagi menyudan kerakli bo'limni tanlang:"
)

REFERRAL_MENU_TITLE = "👥 <b>Do'stlarni taklif qilish</b>\n\n"
REFERRAL_POINTS = "📊 <b>Sizning ballaringiz:</b> {points} ball\n\n"
REFERRAL_DESC = (
    "Har bir sizning havolangiz orqali ro'yxatdan o'tgan do'stingiz uchun siz <b>5 ball</b> olasiz.\n\n"
    "<b>Sizning havolangiz:</b>\n"
    "<a href=\"{referral_link}\">Referall link</a>\n\n"
    "Reytingni ko'rish uchun asosiy menyuda <b>🏆 Reyting</b> tugmasini bosing."
)

LEADERBOARD_TITLE = "🏆 <b>Reyting</b> (referral ballari bo'yicha)\n\n"
LEADERBOARD_EMPTY = "Reyting hali bo'sh.\n"
LEADERBOARD_USER_RANK = "Sizning o'rningiz: <b>{rank}</b> — <b>{user_points}</b> ta"

CHECK_SUBS_FAIL = "❌ <b>Siz hali quyidagi kanallarga obuna bo'lmadingiz:</b>"
CHECK_SUBS_SUCCESS = "✅ <b>Obuna tasdiqlandi!</b>\n\n/start buyrug'ini bosing."
CHECK_SUBS_START = "🌟 Olimpiadaga bog'liq barcha yangiliklardan boxabar bo'lish uchun quyidagi kanallarni ulanib oling:"
CHECK_SUBS_CONFIRMED_ANSWER = "✅ Obuna tasdiqlandi!"
CHECK_SUBS_NOT_CONFIRMED = "❌ Obuna tasdiqlanmadi"

ERROR_NOT_REGISTERED = "❌ Avval ro'yxatdan o'ting!"
ERROR_DATE_FORMAT_EDIT = "❌ Noto'g'ri sana formati. (dd.mm.YYYY)"
ERROR_INVALID_FILE_OR_SKIP = "❌ Iltimos, fayl yoki rasm yuboring yoki 'O'tkazib yuborish' tugmasini bosing:"

MENU_PROMPT = "Quyidagi menyudan kerakli bo'limni tanlang:"

EDIT_TITLE = "<b>✏️ Tahrirlash</b>\n\nQaysi maydonni o'zgartirmoqchisiz?"
EDIT_PROMPT_PREFIX = "Iltimos, yangi"
EDIT_PROMPT_DEFAULT = "Iltimos, yangi ma'lumot kiriting:"
EDIT_FIELD_SUFFIXES = {
    "first_name": "ism kiriting:",
    "last_name": "familiya kiriting:",
    "date_of_birth": "tug'ilgan sana kiriting (dd.mm.YYYY):",
    "document_number": "metrika raqami kiriting:",
    "region": "viloyat tanlang:",
    "district": "tuman/shahar kiriting:",
    "school_name": "maktab nomi kiriting:",
    "grade": "sinf tanlang:",
    "photo": "rasm yuboring:",
    "achievements_description": "avvalgi yutuqlar haqida yozing:",
    "guardian_name": "vasiy ismini kiriting:",
    "guardian_relationship": "vasiy kimligini tanlang:",
    "guardian_phone": "vasiy telefonini kiriting:",
    "teacher_name": "o'qituvchi ismini kiriting:",
    "teacher_phone": "o'qituvchi telefonini kiriting:",
    "source": "manbani tanlang:",
}

OTHER_GRADE_MESSAGE = (
    "Ushbu olimpiadamiz faqat 5-8-sinflar uchun tashkillanmoqda.\n\n"
    "Boshqa sinflar uchun grant imtihonlari yoz oyida bo'lib o'tadi 😊\n\n"
    "Ijtimoiy tarmoqlarimizni kuzatib boring:\n\n"
    "<a href=\"http://t.me/RahimovSchool\">Telegram</a> | <a href=\"https://www.instagram.com/rahimovschool/\">Instagram</a> | <a href=\"https://www.youtube.com/@RahimovSchool\">YouTube</a>"
)


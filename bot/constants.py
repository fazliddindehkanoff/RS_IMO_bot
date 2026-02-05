"""Constant messages for the bot."""

# ==================== GREETING & INTRO ====================

# ==================== STAGE 1: INITIAL REGISTRATION ====================

GREETING_MESSAGE = (
    "👋 Assalomu alaykum!\n\n"
    "Rahimov Matematika Olimpiadasi rasmiy botiga xush kelibsiz 😊\n\n"
    "Botdan foydalanish uchun, avvalo, ro'yxatdan o'tishingiz lozim ✅\n\n"
    "1. Ism-familiyangiz:"
)

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
    "Toshkentdagi eng nufuzli maktablardan biri — Rahimov School xususiy maktabida mutlaqo bepul o'qish imkoniyatiga nima deysiz?\n\n"
    "Viloyatdan bo'lsangiz, yeb-ichish va yotoqxonangizgacha ta'minlab beramiz 🔥\n\n"
    "Maktabimiz haqiqiy vunderkindlarni qidirmoqda 🌟\n\n"
    "\"Rahimov Matematika Olimpiadasi\"da qatnashib, 15 ta grant sohibidan biri bo'ling.\n\n"
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

STEP_2_ASK_SURNAME = (
    "Rahmat, {first_name} 🙌\n\n"
    "Navbat 2-qadamga: Familiyangizni kiriting:"
)

STEP_3_ASK_DOB = (
    "Familiyangiz ham muvaffaqiyatli saqlandi ✅\n\n"
    "Endi, 3-qadam: Qaysi sanada tug'ilgansiz? 😊\n\n"
    "Faqat bitta iltimos, tug'ilgan sanangizni YYYY-MM-DD formatida kiriting, ya'ni: 2010-05-15"
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

STEP_9_ASK_LANGUAGE = (
    "👉 9-qadamga navbat — O'qish tilingizni kiriting:"
)

STEP_10_ASK_PHOTO = (
    "✅ O'qish tilingiz saqlandi:\n\n"
    "Endi, 10-qadam: Rasmingizni yuboring 🖼"
)

# ==================== ACHIEVEMENTS ====================

STEP_11_ASK_ACHIEVEMENTS = (
    "Rasmga gap yo'q 🔥\n\n"
    "11-qadamimiz biroz uzunroq:\n\n"
    "Avvalgi yutuqlaringiz haqida nima deyolasiz?\n\n"
    "(Yutuqlaringiz bo'lmasa, \"O'tkazib yuborish\" tugmasini bosishingiz mumkin)"
)

STEP_12_ASK_ACHIEVEMENTS_FILE = (
    "12-qadamimizda yutuqlaringizning rasmini ham ulashib qo'ysangiz 👏"
)

# ==================== GUARDIAN INFO ====================

STEP_13_ASK_GUARDIAN_NAME = (
    "✅ 13-qadamga keldik:\n\n"
    "Endi vasiyingiz haqida ma'lumotlar so'raymiz 🙂\n\n"
    "Vasiyingiz to'liq ismlarini yozing:"
)

STEP_14_ASK_RELATIONSHIP = (
    "✅ 14-qadam: Kiritilgan vasiy sizga kim? 🙃"
)

STEP_15_ASK_GUARDIAN_AGE = (
    "15-qadam: {relation_text} nechi yoshdalar? 🙂"
)

STEP_16_ASK_GUARDIAN_PROFESSION = (
    "✅ 16-qadam: {relation_text} nima ish qiladilar? Kasblari nima?"
)

STEP_17_ASK_GUARDIAN_PHONE = (
    "17-qadam: {relation_text}ning telefon raqamini kirita olasizmi? 👇"
)

STEP_18_ASK_GUARDIAN_PHONE_2 = (
    "18-qadam: Agar bo'lsa, 2-raqamlarini ham kiritsangiz, bo'lmasa o'tkazib yuborishingiz mumkin 🙂"
)

# ==================== TEACHER INFO ====================

STEP_19_ASK_TEACHER_NAME = (
    "✅ 19-qadamga keldik:\n\n"
    "Endi ustozingiz haqida ma'lumotlar so'raymiz 🙂\n\n"
    "Ustozingiz to'liq ismlarini yozing:"
)
# Note: Reuse this text logic for when phone 2 is entered vs skipped
STEP_19_ASK_TEACHER_NAME_AFTER_PHONE = (
    "✅ 19-qadamga keldik:\n\n"
    "Endi ustozingiz haqida ma'lumotlar so'raymiz 🙂\n\n"
    "Ustozingiz to'liq ismlarini yozing:"
)
STEP_18_PHONE2_SKIPPED_THEN_19 = STEP_19_ASK_TEACHER_NAME_AFTER_PHONE
STEP_18_PHONE2_SAVED_THEN_19 = STEP_19_ASK_TEACHER_NAME_AFTER_PHONE

STEP_20_ASK_TEACHER_WORKPLACE = (
    "✅ 20-qadam: Qayerda ishlaydilar 🙃"
)

STEP_21_ASK_TEACHER_PHONE = (
    "📞 21-qadam: Telefon raqamlarini yozsangiz"
)

# ==================== SOURCE & CONFIRMATION ====================

STEP_22_ASK_SOURCE = (
    "🙌 Oxiridan 1 ta oldingi qadamdamiz — 22-qadam:\n\n"
    "Olimpiadamiz haqida qayerdan eshitdingiz? 🙃"
)

STEP_23_CONFIRMATION_HEADER = (
    "🥳 Nihoyat, eng so'nggi qadam:\n\n"
    "📝 Ushbu ma'lumotlarni tasdiqlaysizmi? 👇\n\n"
)

SUCCESS_MESSAGE = (
    "✅ Rasman! Siz Rahimov Matematika Olimpiadasi ishtirokchisisiz! 🔥\n\n"
    "Bu hali hammasi emas! Sizga olimpiadamiz tomonidan eksklyuziv taklif bor 🤩\n\n"
    "Olimpiadaga tengdoshlaringizni taklif qiling. Eng ko'p taklif qilgan 20 ta o'rin sohibiga quyidagi sovg'alarni va'da qilamiz:\n\n"
    "🥇 1-o'rin: 1 ta mutolaa premium, 1 ta telegram premium va kitoblar to'plami\n"
    "🥈 2-o'rin: 1 ta mutolaa premium, 1 ta telegram premium\n"
    "🥉 3-o'ring: Kitoblar to'plami\n"
    "🎖 4-11-o'rinlarga: 1 ta telegram premium\n"
    "🎖 12-20-o'rinlarga: 1 ta mutolaa premium\n\n"
    "Har bir sizning havolangiz orqali ro'yxatdan o'tgan do'stingiz uchun 5 ball olasiz 🤩\n\n"
    "Rozi bo'lsangiz, \"Ha 🔥\" tugmasini bosing. Biz do'stlaringizga yuborishingiz kerak bo'lgan tayyor xabarni yuboramiz ⚡"
)

PROMO_MESSAGE = (
    "👋 Assalomu alaykum!\n\n"
    "Toshkentdagi eng nufuzli maktablardan biri — <a href=\"http://t.me/rahimovschool\">Rahimov School</a> xususiy maktabida mutlaqo bepul o'qishni istaysizmi?\n\n"
    "Viloyatdan bo'lsangiz, yeb-ichish va yotoqxonangizgacha ta'minlab berisharkan 🔥\n\n"
    "\"Rahimov Matematika Olimpiadasi\"da qatnashib, 15 ta grant sohibidan biri bo'ling.\n\n"
    "Maktab vunderkindlarni qidirmoqda 🔥\n\n"
    "Men ro'yxatdan o'tdim ✅\n\n"
    "Va tayyorlanishni boshlayapman 🙂\n\n"
    "Olimpiadaga haqida batafsil:\n"
    "https://telegra.ph/Rahimov-Matematika-Olimpiadasi-02-05\n\n"
    "Siz ham quyidagi havola orqali ro'yxatdan o'tishingiz mumkin:\n"
    "{referral_link}"
)

REFERRAL_ONLY_PROMO_TEXT = (
    "Vunderkind o'quvchilarga yordam berishga qaror qilganingizdan xursandmiz! 😊\n\n"
    "Olimpiadaga 5-8-sinflarni taklif qiling. Eng ko'p taklif qilgan 20 ta o'rin sohibiga quyidagi sovg'alarni va'da qilamiz:\n\n"
    "🥇 1-o'rin: 1 ta mutolaa premium, 1 ta telegram premium va kitoblar to'plami\n"
    "🥈 2-o'rin: 1 ta mutolaa premium, 1 ta telegram premium\n"
    "🥉 3-o'ring: Kitoblar to'plami\n"
    "🎖 4-11-o'rinlarga: 1 ta telegram premium\n"
    "🎖 12-20-o'rinlarga: 1 ta mutolaa premium\n\n"
    "Har bir sizning havolangiz orqali ro'yxatdan o'tgan do'stingiz uchun 5 ball olasiz 🤩\n\n"
    "Rozi bo'lsangiz, \"Ha 🔥\" tugmasini bosing. Biz do'stlaringizga yuborishingiz kerak bo'lgan tayyor xabarni yuboramiz ⚡"
)

# ==================== ERROR MESSAGES ====================

ERROR_NAME_LENGTH = "❌ Iltimos, to'g'ri ism kiriting (kamida 2 ta belgi):"
ERROR_SURNAME_LENGTH = "❌ Iltimos, to'g'ri familiya kiriting (kamida 2 ta belgi):"
ERROR_DATE_FORMAT = (
    "❌ Iltimos, to'g'ri formatda kiriting (YYYY-MM-DD):\n"
    "Masalan: 2010-05-15"
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
    "<code>{referral_link}</code>\n\n"
    "Reytingni ko'rish uchun asosiy menyuda <b>🏆 Reyting</b> tugmasini bosing."
)

LEADERBOARD_TITLE = "🏆 <b>Reyting</b> (referral ballari bo'yicha)\n\n"
LEADERBOARD_EMPTY = "Reyting hali bo'sh.\n"
LEADERBOARD_USER_RANK = "Sizning o'rningiz: <b>{rank}</b> — <b>{user_points}</b> ball"

CHECK_SUBS_FAIL = "❌ <b>Siz hali quyidagi kanallarga obuna bo'lmadingiz:</b>"
CHECK_SUBS_SUCCESS = "✅ <b>Obuna tasdiqlandi!</b>\n\n/start buyrug'ini bosing."
CHECK_SUBS_START = "❌ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>"
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
    "language": "o'qish tili tanlang:",
    "photo": "rasm yuboring:",
    "achievements_description": "avvalgi yutuqlar haqida yozing:",
    "achievements_file": "yutuqlar rasmini yuboring:",
    "guardian_name": "vasiy ismini kiriting:",
    "guardian_relationship": "vasiy kimligini tanlang:",
    "guardian_age": "vasiy yoshini kiriting:",
    "guardian_profession": "vasiy kasbini kiriting:",
    "guardian_phone": "vasiy telefonini kiriting:",
    "guardian_phone2": "vasiy 2-telefonini kiriting:",
    "teacher_name": "o'qituvchi ismini kiriting:",
    "teacher_workplace": "o'qituvchi ish joyini kiriting:",
    "teacher_phone": "o'qituvchi telefonini kiriting:",
    "source": "manbani tanlang:",
}

OTHER_GRADE_MESSAGE = (
    "Ushbu olimpiadamiz faqat 5-8-sinflar uchun tashkillanmoqda.\n\n"
    "Boshqa sinflar uchun grant imtihonlari yoz oyida bo'lib o'tadi 😊\n\n"
    "Ijtimoiy tarmoqlarimizni kuzatib boring:\n\n"
    "Telegram(http://t.me/RahimovSchool) | Instagram(https://www.instagram.com/rahimovschool/) | YouTube(https://www.youtube.com/@RahimovSchool)"
)

OTHER_GRADE_PROMO_MESSAGE = (
    "Kanalga ulanib oldingizmi?\n\n"
    "Bu hali hammasi emas! Sizga olimpiadamiz tomonidan eksklyuziv taklif bor 🤩\n\n"
    "Olimpiadaga tengdoshlaringizni taklif qiling. Eng ko'p taklif qilgan 20 ta o'rin sohibiga quyidagi sovg'alarni va'da qilamiz:\n\n"
    "🥇 1-o'rin: 1 ta mutolaa premium, 1 ta telegram premium va kitoblar to'plami\n"
    "🥈 2-o'rin: 1 ta mutolaa premium, 1 ta telegram premium\n"
    "🥉 3-o'ring: Kitoblar to'plami\n"
    "🎖 4-11-o'rinlarga: 1 ta telegram premium\n"
    "🎖 12-20-o'rinlarga: 1 ta mutolaa premium\n\n"
    "Har bir sizning havolangiz orqali ro'yxatdan o'tgan do'stingiz uchun 5 ball olasiz 🤩\n\n"
    "Rozi bo'lsangiz, \"Ha 🔥\" tugmasini bosing. Biz do'stlaringizga yuborishingiz kerak bo'lgan tayyor xabarni yuboramiz ⚡"
)

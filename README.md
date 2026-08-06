# Motion Studio AI Frontend

واجهة ثابتة لمشروع Motion Studio AI، متصلة مباشرة بـ RunPod Serverless.

## الملفات

- `index.html`: واجهة المستخدم كاملة.
- `manifest.json`: إعدادات التطبيق على الهاتف.
- `.gitignore`: ملفات لا يجب رفعها إلى GitHub.

## التشغيل

يمكن تشغيل الواجهة عبر:

- Hugging Face Static Space
- GitHub Pages
- Netlify
- Vercel Static Hosting

## إعداد RunPod

داخل الواجهة:

1. أدخل Endpoint ID.
2. أدخل RunPod API Key.
3. اضغط حفظ بيانات الاتصال.
4. ارفع الصورة الأساسية والصورة المرجعية.
5. اكتب البرومبت واضغط تعديل الصورة.

## الأمان

مفتاح RunPod لا يُحفظ داخل GitHub أو داخل ملفات المشروع. يتم حفظه محليًا داخل المتصفح فقط.

قبل إطلاق الموقع للعامة، انقل الاتصال بـ RunPod إلى Backend آمن حتى لا يظهر المفتاح للمستخدمين.

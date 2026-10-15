import os
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
import cv2
import numpy as np
import telebot
from telebot.types import InputMediaPhoto
import mediapipe as mp

# ضع هنا معرف قناتك على تليجرام (مثال: @al_israa_office)
CHANNEL_USERNAME = "@al_israa_office"

TOKEN = os.environ.get("BOT_TOKEN", "8883594752:AAEQttG-Rxg65ur0XrwLzvq1rSpjc-trRAM")
bot = telebot.TeleBot(TOKEN)

mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=True, model_complexity=1)


def process_and_watermark(image_path, output_path):
  img = cv2.imread(image_path)
  if img is None:
    return False

  h, w, _ = img.shape
  img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
  results = pose.process(img_rgb)

  if results.pose_landmarks:
    landmarks = results.pose_landmarks.landmark

    def blur_box(ymin, xmin, ymax, xmax):
      ymin = max(0, int(ymin * h))
      xmin = max(0, int(xmin * w))
      ymax = min(h, int(ymax * h))
      xmax = min(w, int(xmax * w))
      if ymax > ymin and xmax > xmin:
        roi = img[ymin:ymax, xmin:xmax]
        roi = cv2.GaussianBlur(roi, (51, 51), 30)
        img[ymin:ymax, xmin:xmax] = roi

    nose = landmarks[mp_pose.PoseLandmark.NOSE]
    l_sh = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
    r_sh = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
    blur_box(
        nose.y - 0.25,
        min(l_sh.x, r_sh.x) - 0.15,
        max(l_sh.y, r_sh.y) + 0.05,
        max(l_sh.x, r_sh.x) + 0.15,
    )

    l_hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP]
    r_hip = landmarks[mp_pose.PoseLandmark.RIGHT_HIP]
    blur_box(
        min(l_sh.y, r_sh.y),
        min(l_sh.x, r_sh.x) - 0.1,
        max(l_hip.y, r_hip.y),
        max(l_sh.x, r_sh.x) + 0.1,
    )

    for wrist_idx in [
        mp_pose.PoseLandmark.LEFT_WRIST,
        mp_pose.PoseLandmark.RIGHT_WRIST,
    ]:
      wrist = landmarks[wrist_idx]
      if wrist.visibility > 0.4:
        blur_box(
            wrist.y - 0.08, wrist.x - 0.08, wrist.y + 0.08, wrist.x + 0.08
        )

    blur_box(
        min(l_hip.y, r_hip.y) - 0.05,
        min(l_hip.x, r_hip.x) - 0.1,
        max(l_hip.y, r_hip.y) + 0.1,
        max(l_hip.x, r_hip.x) + 0.1,
    )

  img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
  draw = ImageDraw.Draw(img_pil)

  text = "صلي على النبي"
  reshaped_text = arabic_reshaper.reshape(text)
  bidi_text = get_display(reshaped_text)

  try:
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
  except:
    font = ImageFont.load_default()

  bbox = draw.textbbox((0, 0), bidi_text, font=font)
  text_w = bbox[2] - bbox[0]
  text_h = bbox[3] - bbox[1]

  x = w - text_w - 25
  y = h - text_h - 25

  overlay = Image.new("RGBA", img_pil.size, (0, 0, 0, 0))
  draw_overlay = ImageDraw.Draw(overlay)
  draw_overlay.rectangle(
      [x - 12, y - 6, x + text_w + 12, y + text_h + 6], fill=(0, 0, 0, 160)
  )
  img_pil = Image.alpha_composite(img_pil.convert("RGBA"), overlay)
  draw = ImageDraw.Draw(img_pil)
  draw.text((x, y), bidi_text, font=font, fill=(255, 255, 255, 255))

  final_img = cv2.cvtColor(np.array(img_pil.convert("RGB")), cv2.COLOR_RGB2BGR)
  cv2.imwrite(output_path, final_img)
  return True


@bot.message_handler(content_types=["photo"])
def handle_photos(message):
  try:
    msg = bot.reply_to(message, "⏳ جاري تعديل الصورة ونشرها في القناة...")

    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    input_path = f"input_{message.chat.id}.jpg"
    output_path = f"output_{message.chat.id}.jpg"

    with open(input_path, "wb") as new_file:
      new_file.write(downloaded_file)

    success = process_and_watermark(input_path, output_path)

    if success:
      caption = message.caption if message.caption else ""
      caption += "\n\n✨ صلي على النبي"

      target_chat = (
          CHANNEL_USERNAME
          if CHANNEL_USERNAME != "@al_israa_office"
          else message.chat.id
      )

      with open(output_path, "rb") as photo:
        bot.send_photo(target_chat, photo, caption=caption, parse_mode="Markdown")
        bot.delete_message(message.chat.id, msg.message_id)
      bot.reply_to(message, "✅ تم التعديل والنشر بنجاح!")
    else:
      bot.reply_to(message, "عذراً، حدث خطأ أثناء معالجة الصورة.")

    if os.path.exists(input_path):
      os.remove(input_path)
    if os.path.exists(output_path):
      os.remove(output_path)

  except Exception as e:
    bot.reply_to(message, f"حدث خطأ غير متوقع: {str(e)}")


if name == "main":
  print("Bot is up and running...")
  bot.infinity_polling()

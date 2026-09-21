"""
Speaking app utilities
Audio conversion functions
"""
import os
import threading
from shutil import which

from django.conf import settings
from django.core.files.base import ContentFile


def _get_ffmpeg_binary() -> str:
    """
    FFmpeg executable yo'lini aniqlaydi.
    Avval settings.FFMPEG_BIN, keyin which('ffmpeg'), oxirida /usr/bin/ffmpeg fallback.
    """
    # 1) Django settings dan olish (agar berilgan bo'lsa)
    ffmpeg_bin = getattr(settings, "FFMPEG_BIN", None)
    if ffmpeg_bin:
        return ffmpeg_bin

    # 2) PATH orqali qidirish
    path_bin = which("ffmpeg")
    if path_bin:
        return path_bin

    # 3) Eng ko'p uchraydigan joy (Ubuntu)
    return "/usr/bin/ffmpeg"


def convert_audio_to_mp3(file_path, output_path=None):
    """
    Har qanday audio faylni MP3 ga convert qilish
    ffmpeg ishlatadi (WebM, WAV, OGG, M4A, va boshqa formatlar)
    
    Args:
        file_path: Audio faylning to'liq yo'li
        output_path: MP3 fayl saqlanish yo'li (optional)
    
    Returns:
        str: MP3 faylning yo'li yoki None agar xatolik bo'lsa
    """
    try:
        import subprocess

        ffmpeg_bin = _get_ffmpeg_binary()

        # ffmpeg mavjudligini tekshirish
        try:
            subprocess.run(
                [ffmpeg_bin, "-version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            print(f"FFmpeg topilmadi yoki ishga tushmadi: {e}. "
                  "FFmpeg o'rnatilganligini va FFMPEG_BIN sozlamasini tekshiring.")
            return None
        
        # Output path ni aniqlash
        if output_path is None:
            # Original fayl nomidan .mp3 yaratish
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_path = os.path.join(
                os.path.dirname(file_path),
                f"{base_name}.mp3"
            )
        
        # Har qanday audio formatni MP3 ga convert qilish
        # -i: input file
        # -acodec libmp3lame: MP3 codec
        # -ab 192k: audio bitrate
        # -ar 44100: sample rate
        # -ac 2: stereo (2 channels)
        # -y: overwrite output file
        cmd = [
            ffmpeg_bin,
            "-i",
            file_path,
            "-acodec",
            "libmp3lame",
            "-ab",
            "192k",
            "-ar",
            "44100",
            "-ac",
            "2",  # stereo
            "-y",  # overwrite output file
            output_path,
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minut timeout
        )
        
        if result.returncode == 0 and os.path.exists(output_path):
            return output_path
        else:
            print(f"FFmpeg xatosi: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"Audio conversion xatosi: {str(e)}")
        return None


def convert_audio_to_mp3_sync(instance):
    """
    Sinxron har qanday audio formatni MP3 ga convert qilish (darhol)
    Faqat MP3 bo'lmagan audio formatlarni convert qiladi
    
    Args:
        instance: SpeakingUserAnswer model instance
    
    Returns:
        bool: Muvaffaqiyatli convert qilingan bo'lsa True
    """
    try:
        if not instance.record:
            return False
        
        file_path = instance.record.path
        file_name = str(instance.record.name).lower() if instance.record.name else ""
        
        # MP3 fayllarni o'tkazib yuborish
        if file_name.endswith('.mp3'):
            return False
        
        # Audio formatlarni tekshirish (MP3 dan boshqa)
        audio_extensions = ['.webm', '.wav', '.ogg', '.m4a', '.aac', '.flac', '.wma', '.aiff', '.amr', '.3gp']
        is_audio = any(file_name.endswith(ext) for ext in audio_extensions)
        
        # Agar extension yo'q bo'lsa yoki binary bo'lsa, ffmpeg formatni aniqlaydi
        # Shuning uchun har qanday faylni convert qilishga harakat qilamiz
        # Lekin faqat MP3 bo'lmagan fayllarni
        
        # Fayl mavjudligini tekshirish
        if not os.path.exists(file_path):
            print(f"Fayl topilmadi: {file_path}")
            return False
        
        # MP3 fayl yo'lini aniqlash
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        mp3_filename = f"{base_name}.mp3"
        mp3_path = os.path.join(os.path.dirname(file_path), mp3_filename)
        
        # Convert qilish
        converted_path = convert_audio_to_mp3(file_path, mp3_path)
        
        if converted_path and os.path.exists(converted_path):
            # MP3 faylni o'qish
            with open(converted_path, 'rb') as mp3_file:
                mp3_content = mp3_file.read()
            
            # Original fayl nomini saqlab, faqat extension ni o'zgartirish
            original_name = instance.record.name
            mp3_name = os.path.splitext(original_name)[0] + '.mp3'
            
            # Instance ni qayta yuklash
            instance.refresh_from_db()
            
            # MP3 faylni saqlash (original WebM ni almashtirish)
            instance.record.save(
                mp3_name,
                ContentFile(mp3_content),
                save=True
            )
            
            # Original audio faylni o'chirish (agar hali mavjud bo'lsa)
            try:
                if os.path.exists(file_path) and file_path != instance.record.path:
                    os.remove(file_path)
            except Exception as e:
                print(f"Original audio faylni o'chirishda xatolik: {str(e)}")
            
            # Temporary MP3 faylni o'chirish (agar saqlangan fayl bilan bir xil bo'lmasa)
            try:
                if converted_path != instance.record.path and os.path.exists(converted_path):
                    os.remove(converted_path)
            except Exception as e:
                print(f"Temporary MP3 faylni o'chirishda xatolik: {str(e)}")
            
            print(f"Audio muvaffaqiyatli MP3 ga convert qilindi: {instance.id}")
            return True
        else:
            print(f"Audio convert qilishda xatolik: {instance.id}")
            return False
            
    except Exception as e:
        print(f"Sync conversion xatosi: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def convert_audio_to_mp3_async(instance):
    """
    Background thread da har qanday audio formatni MP3 ga convert qilish
    Faqat MP3 bo'lmagan audio formatlarni convert qiladi
    
    Args:
        instance: SpeakingUserAnswer model instance
    """
    def convert_task():
        try:
            # Instance ni qayta yuklash (database dan yangi ma'lumot olish)
            from apps.speaking.models import SpeakingUserAnswer
            try:
                instance.refresh_from_db()
            except:
                return
            
            if not instance.record:
                return
            
            file_path = instance.record.path
            file_name = str(instance.record.name).lower() if instance.record.name else ""
            
            # MP3 fayllarni o'tkazib yuborish
            if file_name.endswith('.mp3'):
                return
            
            # Audio formatlarni tekshirish (MP3 dan boshqa)
            audio_extensions = ['.webm', '.wav', '.ogg', '.m4a', '.aac', '.flac', '.wma', '.aiff', '.amr', '.3gp']
            is_audio = any(file_name.endswith(ext) for ext in audio_extensions)
            
            # Agar extension yo'q bo'lsa yoki binary bo'lsa, ffmpeg formatni aniqlaydi
            # Shuning uchun har qanday faylni convert qilishga harakat qilamiz
            # Lekin faqat MP3 bo'lmagan fayllarni
            
            # Fayl mavjudligini tekshirish
            if not os.path.exists(file_path):
                print(f"Fayl topilmadi: {file_path}")
                return
            
            # MP3 fayl yo'lini aniqlash
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            mp3_filename = f"{base_name}.mp3"
            mp3_path = os.path.join(os.path.dirname(file_path), mp3_filename)
            
            # Convert qilish
            converted_path = convert_audio_to_mp3(file_path, mp3_path)
            
            if converted_path and os.path.exists(converted_path):
                # MP3 faylni o'qish
                with open(converted_path, 'rb') as mp3_file:
                    mp3_content = mp3_file.read()
                
                # Original fayl nomini saqlab, faqat extension ni o'zgartirish
                original_name = instance.record.name
                mp3_name = os.path.splitext(original_name)[0] + '.mp3'
                
                # Instance ni qayta yuklash
                instance.refresh_from_db()
                
                # MP3 faylni saqlash (original WebM ni almashtirish)
                instance.record.save(
                    mp3_name,
                    ContentFile(mp3_content),
                    save=True
                )
                
                # Original audio faylni o'chirish (agar hali mavjud bo'lsa)
                try:
                    if os.path.exists(file_path) and file_path != instance.record.path:
                        os.remove(file_path)
                except Exception as e:
                    print(f"Original audio faylni o'chirishda xatolik: {str(e)}")
                
                # Temporary MP3 faylni o'chirish (agar saqlangan fayl bilan bir xil bo'lmasa)
                try:
                    if converted_path != instance.record.path and os.path.exists(converted_path):
                        os.remove(converted_path)
                except Exception as e:
                    print(f"Temporary MP3 faylni o'chirishda xatolik: {str(e)}")
                
                print(f"Audio muvaffaqiyatli MP3 ga convert qilindi: {instance.id}")
            else:
                print(f"Audio convert qilishda xatolik: {instance.id}")
                
        except Exception as e:
            print(f"Background conversion xatosi: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Background thread yaratish
    thread = threading.Thread(target=convert_task, daemon=True)
    thread.start()
    return thread


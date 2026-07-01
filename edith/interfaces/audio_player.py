import sys
import time
import pygame

def main():
    if len(sys.argv) < 2:
        print("Usage: python audio_player.py <filepath>")
        sys.exit(1)
        
    filepath = sys.argv[1]
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
        pygame.mixer.music.unload()
        pygame.mixer.quit()
    except Exception as e:
        print(f"Error playing audio: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()

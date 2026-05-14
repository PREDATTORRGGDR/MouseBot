import json
import time
from pathlib import Path

from pynput import keyboard, mouse


PATTERN_FILE = Path(__file__).with_name("mouse_pattern.json")

recording = False
playing = False
events = []
record_start = 0.0
last_move_time = 0.0

mouse_controller = mouse.Controller()


def now():
    return time.perf_counter()


def save_events():
    PATTERN_FILE.write_text(
        json.dumps(events, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_events():
    if not PATTERN_FILE.exists():
        print(f"Файл записи не найден: {PATTERN_FILE}")
        return []

    return json.loads(PATTERN_FILE.read_text(encoding="utf-8"))


def add_event(event):
    if not recording or playing:
        return

    event["t"] = now() - record_start
    events.append(event)


def on_move(x, y):
    global last_move_time

    if not recording or playing:
        return

    current_time = now()

    # Чтобы файл не раздувался слишком сильно, пишем движение раз в 10 мс.
    if current_time - last_move_time < 0.01:
        return

    last_move_time = current_time
    add_event({"type": "move", "x": x, "y": y})


def on_click(x, y, button, pressed):
    add_event(
        {
            "type": "click",
            "x": x,
            "y": y,
            "button": button.name,
            "pressed": pressed,
        }
    )


def on_scroll(x, y, dx, dy):
    add_event({"type": "scroll", "x": x, "y": y, "dx": dx, "dy": dy})


def start_recording():
    global recording, events, record_start, last_move_time

    events = []
    recording = True
    record_start = now()
    last_move_time = 0.0
    print("Запись началась. Двигай мышь, кликай, крути колесо. F8 - остановить.")


def stop_recording():
    global recording

    recording = False
    save_events()
    print(f"Запись остановлена. Событий: {len(events)}")
    print(f"Файл: {PATTERN_FILE}")


def play_events():
    global playing

    if recording:
        print("Сначала останови запись на F8.")
        return

    recorded_events = load_events()
    if not recorded_events:
        print("Запись пустая. Нажми F8, запиши движения, потом снова F6.")
        return

    playing = True
    print(f"Воспроизведение началось. Событий: {len(recorded_events)}")

    start_time = now()
    for event in recorded_events:
        wait_time = event["t"] - (now() - start_time)
        if wait_time > 0:
            time.sleep(wait_time)

        event_type = event["type"]

        if event_type == "move":
            mouse_controller.position = (event["x"], event["y"])
        elif event_type == "click":
            button = getattr(mouse.Button, event["button"])
            mouse_controller.position = (event["x"], event["y"])
            if event["pressed"]:
                mouse_controller.press(button)
            else:
                mouse_controller.release(button)
        elif event_type == "scroll":
            mouse_controller.position = (event["x"], event["y"])
            mouse_controller.scroll(event["dx"], event["dy"])

    playing = False
    print("Воспроизведение закончено.")


def on_key_press(key):
    try:
        if key == keyboard.Key.f8:
            if recording:
                stop_recording()
            else:
                start_recording()

        elif key == keyboard.Key.f6:
            play_events()

        elif key == keyboard.Key.esc:
            print("Выход.")
            return False

    except Exception as error:
        print(f"Ошибка: {error}")


def main():
    print("Mouse recorder запущен.")
    print("F8 - начать/остановить запись")
    print("F6 - воспроизвести запись")
    print("Esc - выйти")
    print(f"Файл записи: {PATTERN_FILE}")

    mouse_listener = mouse.Listener(
        on_move=on_move,
        on_click=on_click,
        on_scroll=on_scroll,
    )
    keyboard_listener = keyboard.Listener(on_press=on_key_press)

    mouse_listener.start()
    keyboard_listener.start()
    keyboard_listener.join()
    mouse_listener.stop()


if __name__ == "__main__":
    main()

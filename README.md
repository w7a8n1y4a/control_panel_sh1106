# Control Panel SH1106

Parameter | Implementation
-- | --
Description | Принимает base64-кодированные кадры по `MQTT` и отображает их на `OLED` дисплее `SH1106` через `I2C`. Опционально поддерживает энкодер с кнопкой для публикации действий в топик `encoder_action/pepeunit`
Lang | `Micropython`
Hardware | `esp32`, `esp32c3`, `esp32s3`, `esp8266`, `SH1106`, `KY-040`, `encoder`, `button`
Firmware | [RELEASE-1.1.1](https://git.pepemoss.com/pepe/pepeunit/libs/pepeunit_micropython_client/-/releases/1.1.1)
Stack | `pepeunit_micropython_client`
Version | 1.1.1
License | AGPL v3 License
Authors | Ivan Serebrennikov <admin@silberworks.com>

## Example
[![Watch Demo ▶️](https://img.youtube.com/vi/r1CpkXD_MJY/0.jpg)](https://www.youtube.com/watch?v=r1CpkXD_MJY)

## Schema

<div align="center"><img align="center" src="https://minio.pepemoss.com/public-data/image/control_panel_sh1106.png"></div>

## Files

1. [Модель v3, капсулы](https://minio.pepemoss.com/public-data/model/control_panel_sh1106/v3/stl/capsule_insert.stl)
2. [Модель v3, блока для sh1106](https://minio.pepemoss.com/public-data/model/control_panel_sh1106/v3/stl/capsule_panel.stl)
3. [Модель v3, блока энкодера](https://minio.pepemoss.com/public-data/model/control_panel_sh1106/v3/stl/capsule_encoder.stl)
4. [Модель v3, блока esp32s3 zero](https://minio.pepemoss.com/public-data/model/control_panel_sh1106/v3/stl/capsule_mc_esp32s3_zero.stl)
5. [Модель v3, блока esp32c3 super mini](https://minio.pepemoss.com/public-data/model/control_panel_sh1106/v3/stl/capsule_mc_esp32с3_super_mini.stl)
6. [Модель v3, блока (esp8266) wemos d1 mini](https://minio.pepemoss.com/public-data/model/control_panel_sh1106/v3/stl/capsule_mc_wemos_d1_minii.stl)
7. [Модель v3, внешней оболочки капсулы](https://minio.pepemoss.com/public-data/model/control_panel_sh1106/v3/stl/capsule_casing.stl)

## Physical IO

- `client.settings.PIN_SCL` - Вывод `SCL` шины `I2C` для дисплея
- `client.settings.PIN_SDA` - Вывод `SDA` шины `I2C` для дисплея
- `client.settings.PIN_BUTTON` - Вывод кнопки (работает только при `FF_ENCODER_ENABLE` = `true`)
- `client.settings.PIN_ENCODER_CLK` - Вывод `CLK` энкодера (работает только при `FF_ENCODER_ENABLE` = `true`)
- `client.settings.PIN_ENCODER_DT` - Вывод `DT` энкодера (работает только при `FF_ENCODER_ENABLE` = `true`)

## Env variable assignment

1. `FREQ` - Частота процессора в Гц
2. `FF_ENCODER_ENABLE` - Включить энкодер: `true` или `false`
3. `PIN_SCL` - Номер пина `SCL` шины `I2C`
4. `PIN_SDA` - Номер пина `SDA` шины `I2C`
5. `I2C_FREQUENCY` - Частота шины I2C в Гц
6. `I2C_ADDRESS` - I2C адрес дисплея в формате `"0x3c"`
7. `DISPLAY_WIDTH` - Ширина дисплея в пикселях
8. `DISPLAY_HEIGHT` - Высота дисплея в пикселях
9. `PIN_BUTTON` - Номер пина кнопки
10. `PIN_ENCODER_CLK` - Номер пина `CLK` энкодера
11. `PIN_ENCODER_DT` - Номер пина `DT` энкодера
12. `BUTTON_DEBOUNCE_TIME` - Время антидребезга кнопки в миллисекундах
13. `BUTTON_DOUBLE_CLICK_TIME` - Окно для двойного клика в миллисекундах
14. `BUTTON_LONG_PRESS_TIME` - Время долгого нажатия в миллисекундах
15. `ENCODER_STEPS_PER_DETENT` - Количество шагов энкодера на один щелчок
16. `PUC_WIFI_SSID` - Имя сети `WiFi`
17. `PUC_WIFI_PASS` - Пароль от сети `WiFi`

## Assignment of Device Topics

- `full_frame/pepeunit` - Принимает base64-кодированный кадр (входящий) для отображения на дисплее `SH1106`
- `encoder_action/pepeunit` - Отправляет действие энкодера текстом: `One`, `Double`, `Long` (кнопка) или `Right`, `Left` (вращение)

## Work algorithm

1. Подключение к `WiFi`
2. Подключение к `MQTT` Брокеру
3. Синхронизация времени по `NTP`
4. Инициализация `I2C` шины и дисплея `SH1106`
5. Инициализация энкодера и кнопки (если `FF_ENCODER_ENABLE` = `true`)
6. Подписка на входящие `MQTT` топики
7. При получении сообщения в `full_frame/pepeunit`: декодирование `base64` и отрисовка кадра на дисплее
8. При нажатии кнопки или вращении энкодера: публикация действия в `encoder_action/pepeunit` (`One`, `Double`, `Long`, `Right`, `Left`)
9. Для `esp8266` рекомендуется использовать `FF_ENCODER_ENABLE` = `false`, а также частоту кристалла `160000000`, при этом ограничив `fps` источника кадров `10 fps`

## Installation

1. Установите образ `Micropython` указанный в `firmware` на одну из платформ, например для `esp32` как это сделано в [руководстве](https://micropython.org/download/ESP32_GENERIC/)
2. Создайте `Unit` в `Pepeunit`
3. Установите переменные окружения в `Pepeunit`
4. Скачайте архив c программой из `Pepeunit`
5. Распакуйте архив в директорию
6. Загрузите файлы из директории на физическое устройство, например командой: `ampy -p /dev/ttyUSB0 -b 115200 put ./ .`
7. Запустить устройство нажатием кнопки `reset`

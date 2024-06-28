import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import threading
import time

import sys
import time
import requests
from hx711py.hx711 import HX711

from logging import getLogger
from time import sleep
import argparse
import smbus
import json
#####################start#####################
#$ source venvfb/bin/activate
#$ python3 i_main_2.py
#####################start#####################
ADDRESS = 0x44

COMMAND_MEAS_HIGHREP = 0x2C
COMMAND_RESULT = 0x00


# プログラムが中断された時に呼び出される関数
def cleanAndExit():
    print("クリーニング中")
    hx.power_down()  # HX711をパワーダウンする
    hx.reset()       # HX711をリセットしてゼロにする
    print("終了！")
    sys.exit()# プログラムを終了する

# HX711とピンの設定
hx = HX711(5, 6)  # DTピン = 5, SCKピン = 6
hx.set_reading_format("MSB", "MSB")  # HX711の読み取り形式を設定

# 重量センサーのキャリブレーション値
hx.set_reference_unit(391)

hx.reset()  # HX711をリセットしてゼロにする
hx.tare()   # ゼロ点を設定する
print("ゼロ点設定完了！重量データを取得中")



class SHT31(object):
    def __init__(self, address=ADDRESS):
        self._logger = getLogger(self.__class__.__name__)
        self._address = address
        self._bus = smbus.SMBus(1)

        self._logger.debug("SHT31 sensor is starting...")

    def get_temperature(self):
        """Read the temperature from the sensor and return it."""
        temperature, humidity = self.get_temperature_humidity()
        return temperature

    def get_humidity(self):
        """Read the humidity from the sensor and return it."""
        temperature, humidity = self.get_temperature_humidity()
        return humidity

    def get_temperature_humidity(self):
        self.write_list(COMMAND_MEAS_HIGHREP, [0x06])
        sleep(0.5)

        data = self.read_list(COMMAND_RESULT, 6)
        temperature = -45 + (175 * (data[0] * 256 + data[1]) / 65535.0)
        humidity = 100 * (data[3] * 256 + data[4]) / 65535.0

        return round(temperature ,2), round(humidity, 2)

    def read(self, register):
        return self._bus.read_byte_data(self._address, register) & 0xFF

    def read_list(self, register, length):
        return self._bus.read_i2c_block_data(self._address, register, length)

    def write(self, register, value):
        value = value & 0xFF
        self._bus.write_byte_data(self._address, register, value)

    def write_list(self, register, data):
        self._bus.write_i2c_block_data(self._address, register, data)

#####################sensor#####################
#####################sensor#####################


# # Firebaseの認証情報を設定（サービスアカウントキーのパス）
# cred = credentials.Certificate('./react-iot-290ee-firebase-adminsdk-nhprq-965468b4a6.json')
# firebase_admin.initialize_app(cred)

# # Firestoreクライアントを初期化
# db = firestore.client()

# 監視するドキュメントの参照
########################↓設定類↓########################
theRspId = "*****************"
init_aver_count = 30
########################↑設定類↑########################
# Firebaseの認証情報を指定
cred = credentials.Certificate("./*****************.json")

# Firebaseが初期化されていない場合のみ初期化する
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()
rasp_ref = db.collection('rasp').document(theRspId)
meas_ref = db.collection('meas')
# ループBを管理するためのフラグ
loopB_running = False
minu_value = 10
rate_value = 92
init_weight = 0
meas_id = ""
loobB_count = 0
init_w_sample = []
# init_weight_set_count
def loopB():
    global loopB_running
    global minu_value
    global rate_value
    global init_weight
    global meas_id
    global init_w_sample
    sht31 = SHT31()
    while init_weight == 0:
        print('init_weightセッティング中')
        initialising_weight = round(hx.get_weight(5), 2)

        print(f'initialising_weight:{initialising_weight}')
        if initialising_weight > 5 and len(init_w_sample) < init_aver_count:
            init_w_sample.append(initialising_weight)
            print(f'init_w_sample:{init_w_sample}')
        elif len(init_w_sample) >= init_aver_count:
            total = sum(init_w_sample)
            count = len(init_w_sample)
            average = total / count
            init_weight = average
            print(f'init_weight = average:{init_weight}')
        time.sleep(0.1)
    while loopB_running:
        # ループBの処理（関数A_()を実行する例）
        print("Executing function A_()")
        print(f"LoopB::minu: {minu_value}, rate: {rate_value}")
        # ここに関数A_()の実際の処理を記述
        weight = round(hx.get_weight(5), 2)
        temperature, humidity = sht31.get_temperature_humidity()
        sensData = {
            "weight": weight,
            "temp": temperature,
            "humi": humidity,
            "raspId": theRspId,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "measId": meas_id,
            "initWght":round(init_weight, 2),
            "rate":rate_value,
        }
        data_ref = db.collection("data").add(sensData)
        print(sensData)
        hx.power_down()  # HX711をパワーダウンする
        hx.power_up()
        #time.sleep(5)
        time.sleep(int(minu_value)*60)  # 例示的な処理のための待機

# ドキュメントの変更を監視するコールバック
def on_snapshot(doc_snapshot, changes, read_time):
    global loopB_running
    global minu_value
    global rate_value
    global init_weight
    global meas_id
    global init_w_sample
    for change in changes:
        if change.type.name == 'MODIFIED':
            doc_data = change.document.to_dict()
            status = doc_data.get('status')
            meas_id = doc_data.get('measId')
            print(f"measId: {meas_id}")
            # minu_value = 600
            # rate_value = 90

            # measコレクションからminuとrateを取得する
            if meas_id:
                meas_doc = meas_ref.document(meas_id).get().to_dict()
                if meas_doc:
                    minu_value = meas_doc.get('minu')
                    rate_value = meas_doc.get('rate')
                    print(f"minu: {minu_value}, rate: {rate_value}")

            if status == 'on' and not loopB_running:
                print("Starting loop B")
                loopB_running = True
                # ループBを開始するスレッドを起動
                thread = threading.Thread(target=loopB)
                thread.start()
            elif status == 'off' and loopB_running:
                print("Stopping loop B")
                loopB_running = False
                init_weight = 1
                time.sleep(3)
                init_weight = 0 #init_weight初期化
                init_w_sample = []
                print(f'init_weight:{init_weight}')
                print(f'init_w_sample:{init_w_sample}')


# 監視を開始
doc_watch = rasp_ref.on_snapshot(on_snapshot)

try:
    while True:
        # メインの無限ループAはここで何か処理を行う（Firestoreの監視は別スレッドで動作する）
        time.sleep(5)  # 例示的な待機
except KeyboardInterrupt:
    # Ctrl+Cが押されたら、プログラムを終了する
    doc_watch.unsubscribe()
    print("Firestore listener stopped")








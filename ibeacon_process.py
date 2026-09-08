import subprocess
import time

class iBeaconProcess:
    def __init__(self):
        """
        iBeacon処理の初期化。
        """
        self.adv_data_cmd = [
            'sudo', 'hcitool', '-i', 'hci0', 'cmd', '0x08', '0x0008',
            '1E', '02', '01', '1A', '1A', 'FF', '4C', '00', '02', '15',
            'E2', '0A', '39', 'F4', '73', 'F5', '4B', 'C4', 'A1', '2F',
            '17', 'D1', 'AD', '07', 'A9', '61', '00', '01', '00', '96', 'CA', '00'
        ]

    def _run_command(self, command, command_description):
        """
        シェルコマンドを実行し、戻り値をチェックするプライベートメソッド。
        """
        print(f"\n--- {command_description} ---")
        print("Running command:", ' '.join(command))
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode == 0:
            print("Command executed successfully.")
            if result.stdout:
                print("Standard Output:", result.stdout.strip())
        else:
            print(f"Error: Command failed with return code {result.returncode}.")
            if result.stderr:
                print("Standard Error:", result.stderr.strip())
        
        return result

    def start_beacon(self, duration=2):
        """
        iBeaconの発信を開始し、指定された時間（秒）維持します。
        """
        # 1. HCI0デバイスを有効化
        self._run_command(['sudo', 'hciconfig', 'hci0', 'up'], "1. HCIデバイスの有効化")

        # 2. アドバタイズデータのセット
        self._run_command(self.adv_data_cmd, "2. アドバタイズデータのセット")

        # 3. アドバタイズの開始
        self._run_command(['sudo', 'hcitool', '-i', 'hci0', 'cmd', '0x08', '0x000a', '01'], "3. アドバタイズの開始")
        
        print(f"\n--- {duration}秒間ビーコンを発信します ---")
        time.sleep(duration)
        
        # 4. アドバタイズの停止
        self.stop_beacon()

    def stop_beacon(self):
        """
        iBeaconの発信を停止します。
        """
        self._run_command(['sudo', 'hcitool', '-i', 'hci0', 'cmd', '0x08', '0x000a', '00'], "4. アドバタイズの停止")

# 使用例
if __name__ == "__main__":
    beacon = iBeaconProcess()
    # 2秒間ビーコンを発信
    beacon.start_beacon(duration=1)

import serial
import json
import time
import math

class GimbalController:
    def __init__(self, port='COM3', baudrate=115200):
        """
        初始化云台控制器
        
        Args:
            port: 串口端口号，例如 'COM3' (Windows) 或 '/dev/ttyUSB0' (Linux)
            baudrate: 波特率，默认115200
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.frequency = 1  # 改为1Hz
        self.interval = 1.0 / self.frequency  # 1.0秒
        
        # 云台控制参数
        self.current_x = 0
        self.current_y = 0
        self.target_x = 0
        self.target_y = 0
        self.speed = 50
        self.acceleration = 10
        
        # 运动模式
        self.motion_mode = 'manual'  # 'manual', 'circle', 'square', 'scan'
        
    def connect(self):
        """连接串口"""
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"已连接到 {self.port}, 波特率: {self.baudrate}")
            time.sleep(2)  # 等待连接稳定
            return True
        except serial.SerialException as e:
            print(f"串口连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开串口连接"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            print("串口已断开")
    
    def send_gimbal_command(self, x, y, spd=None, acc=None):
        """
        发送云台控制指令
        
        Args:
            x: 水平角度 (-180 到 180)
            y: 垂直角度 (-30 到 90)
            spd: 速度 (可选)
            acc: 加速度 (可选)
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            print("串口未连接")
            return False
        
        # 限制角度范围
        x = max(-180, min(180, x))
        y = max(-30, min(90, y))
        
        # 使用默认值或传入值
        speed = spd if spd is not None else self.speed
        acceleration = acc if acc is not None else self.acceleration
        
        # 构造JSON命令
        command = {
            "T": 133,  # CMD_GIMBAL_CTRL_SIMPLE
            "X": x,
            "Y": y,
            "SPD": speed,
            "ACC": acceleration
        }
        
        try:
            # 发送JSON命令
            json_str = json.dumps(command) + '\n'
            self.serial_conn.write(json_str.encode('utf-8'))
            print(f"发送指令: X={x:6.1f}°, Y={y:6.1f}°, SPD={speed}, ACC={acceleration}")
            return True
        except Exception as e:
            print(f"发送指令失败: {e}")
            return False
    
    def set_target_position(self, x, y):
        """设置目标位置"""
        self.target_x = max(-180, min(180, x))
        self.target_y = max(-30, min(90, y))
    
    def manual_control(self):
        """手动控制模式"""
        print("\n=== 手动控制模式 ===")
        print("输入格式: x,y (例如: 45,30)")
        print("输入 'q' 退出")
        
        while True:
            try:
                user_input = input("输入目标位置 (x,y): ").strip()
                if user_input.lower() == 'q':
                    break
                
                x, y = map(float, user_input.split(','))
                self.set_target_position(x, y)
                print(f"目标位置设置为: X={self.target_x}°, Y={self.target_y}°")
                
            except ValueError:
                print("输入格式错误，请输入: x,y")
            except KeyboardInterrupt:
                break
    
    def circle_motion(self, center_x=0, center_y=30, radius=45, duration=10):
        """圆形运动模式"""
        print(f"\n=== 圆形运动模式 ===")
        print(f"中心: ({center_x}°, {center_y}°), 半径: {radius}°, 持续时间: {duration}秒")
        
        start_time = time.time()
        
        while time.time() - start_time < duration:
            # 计算当前时间对应的角度
            elapsed = time.time() - start_time
            angle = 2 * math.pi * elapsed / duration
            
            # 计算圆形轨迹上的点
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * 0.5 * math.sin(angle)  # Y轴范围较小，缩放0.5
            
            self.send_gimbal_command(x, y)
            time.sleep(self.interval)
    
    def square_motion(self, center_x=0, center_y=30, size=60, duration=8):
        """方形运动模式"""
        print(f"\n=== 方形运动模式 ===")
        print(f"中心: ({center_x}°, {center_y}°), 边长: {size}°, 持续时间: {duration}秒")
        
        # 定义方形的四个顶点
        half_size = size / 2
        points = [
            (center_x - half_size, center_y - half_size/2),  # 左下
            (center_x + half_size, center_y - half_size/2),  # 右下
            (center_x + half_size, center_y + half_size/2),  # 右上
            (center_x - half_size, center_y + half_size/2),  # 左上
        ]
        
        points_per_side = int(duration * self.frequency / 4)  # 每边的点数
        
        for i in range(4):  # 四条边
            start_point = points[i]
            end_point = points[(i + 1) % 4]
            
            for j in range(points_per_side):
                # 线性插值
                t = j / points_per_side
                x = start_point[0] + t * (end_point[0] - start_point[0])
                y = start_point[1] + t * (end_point[1] - start_point[1])
                
                self.send_gimbal_command(x, y)
                time.sleep(self.interval)
    
    def scan_motion(self, scan_range=120, scan_speed=30, duration=10):
        """扫描运动模式"""
        print(f"\n=== 扫描运动模式 ===")
        print(f"扫描范围: ±{scan_range/2}°, 扫描速度: {scan_speed}°/s, 持续时间: {duration}秒")
        
        start_time = time.time()
        
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            
            # 计算扫描位置 (正弦波)
            x = (scan_range / 2) * math.sin(2 * math.pi * elapsed / (scan_range / scan_speed))
            y = 30  # 固定Y轴位置
            
            self.send_gimbal_command(x, y)
            time.sleep(self.interval)
    
    def run_continuous(self):
        """持续运行模式，发送当前目标位置"""
        print(f"\n=== 持续运行模式 ({self.frequency}Hz) ===")
        print("发送目标位置指令，按 Ctrl+C 停止")
        
        try:
            while True:
                self.send_gimbal_command(self.target_x, self.target_y)
                time.sleep(self.interval)
        except KeyboardInterrupt:
            print("\n停止发送指令")
    
    def main_menu(self):
        """主菜单"""
        while True:
            print("\n" + "="*50)
            print(f"云台控制器 - {self.frequency}Hz控制频率")
            print("="*50)
            print("1. 手动控制")
            print("2. 圆形运动")
            print("3. 方形运动")
            print("4. 扫描运动")
            print("5. 持续运行当前目标位置")
            print("6. 设置参数")
            print("7. 回到中心位置")
            print("0. 退出")
            
            choice = input("请选择模式 (0-7): ").strip()
            
            if choice == '1':
                self.manual_control()
            elif choice == '2':
                self.circle_motion()
            elif choice == '3':
                self.square_motion()
            elif choice == '4':
                self.scan_motion()
            elif choice == '5':
                self.run_continuous()
            elif choice == '6':
                self.settings_menu()
            elif choice == '7':
                self.set_target_position(0, 0)
                self.send_gimbal_command(0, 0)
                print("云台回到中心位置")
            elif choice == '0':
                break
            else:
                print("无效选择，请重新输入")
    
    def settings_menu(self):
        """设置菜单"""
        while True:
            print("\n" + "="*30)
            print("参数设置")
            print("="*30)
            print(f"1. 速度: {self.speed}")
            print(f"2. 加速度: {self.acceleration}")
            print(f"3. 发送频率: {self.frequency}Hz")
            print(f"4. 串口: {self.port}")
            print(f"5. 波特率: {self.baudrate}")
            print("0. 返回主菜单")
            
            choice = input("请选择要修改的参数 (0-5): ").strip()
            
            if choice == '1':
                try:
                    self.speed = int(input(f"输入新的速度值 (当前: {self.speed}): "))
                    print(f"速度已设置为: {self.speed}")
                except ValueError:
                    print("输入无效")
            elif choice == '2':
                try:
                    self.acceleration = int(input(f"输入新的加速度值 (当前: {self.acceleration}): "))
                    print(f"加速度已设置为: {self.acceleration}")
                except ValueError:
                    print("输入无效")
            elif choice == '3':
                try:
                    new_frequency = float(input(f"输入新的发送频率 (当前: {self.frequency}Hz): "))
                    if new_frequency > 0:
                        self.frequency = new_frequency
                        self.interval = 1.0 / self.frequency
                        print(f"发送频率已设置为: {self.frequency}Hz (间隔: {self.interval:.3f}秒)")
                    else:
                        print("频率必须大于0")
                except ValueError:
                    print("输入无效")
            elif choice == '4':
                new_port = input(f"输入新的串口 (当前: {self.port}): ").strip()
                if new_port:
                    self.port = new_port
                    print(f"串口已设置为: {self.port}")
                    print("请重新连接串口")
            elif choice == '5':
                try:
                    self.baudrate = int(input(f"输入新的波特率 (当前: {self.baudrate}): "))
                    print(f"波特率已设置为: {self.baudrate}")
                    print("请重新连接串口")
                except ValueError:
                    print("输入无效")
            elif choice == '0':
                break
            else:
                print("无效选择，请重新输入")


def main():
    """主函数"""
    print("云台控制器启动中...")
    
    # 创建控制器实例
    controller = GimbalController()
    
    # 连接串口
    if not controller.connect():
        print("无法连接串口，请检查端口设置")
        return
    
    try:
        # 启动主菜单
        controller.main_menu()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    finally:
        # 断开连接
        controller.disconnect()
        print("程序结束")


if __name__ == "__main__":
    main()
# sound_manager.py - 音效管理模块（无额外依赖版本）
import os
import random
import threading
import time
from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


class SoundManager(QObject):
    """音效管理器"""
    
    def __init__(self):
        super().__init__()
        
        # 背景音乐播放器
        self.bgm_player = QMediaPlayer()
        self.bgm_audio = QAudioOutput()
        self.bgm_player.setAudioOutput(self.bgm_audio)
        self.bgm_audio.setVolume(0.3)  # 背景音乐音量30%
        
        # 音效播放器列表
        self.sfx_players = []
        self.sfx_volume = 0.6  # 音效音量60%
        
        # 音效文件路径
        self.sound_files = {}
        self.bgm_files = []
        
        # 音效开关
        self.bgm_enabled = True
        self.sfx_enabled = True
        
        # 背景音乐循环标志
        self.bgm_loop_running = False
        self.bgm_thread = None
        
        # 初始化音效
        self._init_sounds()
        
        # 设置背景音乐循环
        self.bgm_player.mediaStatusChanged.connect(self._on_bgm_status_changed)
    
    def _init_sounds(self):
        """初始化音效文件路径"""
        # 创建音效目录
        sound_dir = "sounds"
        if not os.path.exists(sound_dir):
            os.makedirs(sound_dir)
            print(f"已创建音效目录: {sound_dir}")
            print("请将音效文件放入 sounds 目录中，或使用内置蜂鸣音效")
        
        # 背景音乐列表
        self.bgm_files = [
            os.path.join(sound_dir, "bgm1.mp3"),
            os.path.join(sound_dir, "bgm2.mp3"),
            os.path.join(sound_dir, "bgm3.mp3"),
        ]
        
        # 音效文件映射
        self.sound_files = {
            # 游戏流程音效
            "start": os.path.join(sound_dir, "start.wav"),
            "win": os.path.join(sound_dir, "win.wav"),
            "lose": os.path.join(sound_dir, "lose.wav"),
            "landlord": os.path.join(sound_dir, "landlord.wav"),
            
            # 出牌音效
            "play_card": os.path.join(sound_dir, "play_card.wav"),
            "play_single": os.path.join(sound_dir, "play_single.wav"),
            "play_pair": os.path.join(sound_dir, "play_pair.wav"),
            "play_triple": os.path.join(sound_dir, "play_triple.wav"),
            "play_straight": os.path.join(sound_dir, "play_straight.wav"),
            "play_bomb": os.path.join(sound_dir, "play_bomb.wav"),
            "play_rocket": os.path.join(sound_dir, "play_rocket.wav"),
            
            # 动作音效
            "pass": os.path.join(sound_dir, "pass.wav"),
            "select": os.path.join(sound_dir, "select.wav"),
            "button_click": os.path.join(sound_dir, "click.wav"),
            
            # 提示音效
            "your_turn": os.path.join(sound_dir, "your_turn.wav"),
            "ai_turn": os.path.join(sound_dir, "ai_turn.wav"),
            "hurry": os.path.join(sound_dir, "hurry.wav"),
        }
        
        # 牌型对应的音效
        self.card_type_sounds = {
            "SINGLE": "play_single",
            "PAIR": "play_pair",
            "TRIPLE": "play_triple",
            "TRIPLE_WITH_ONE": "play_triple",
            "TRIPLE_WITH_PAIR": "play_triple",
            "STRAIGHT": "play_straight",
            "DOUBLE_STRAIGHT": "play_straight",
            "TRIPLE_STRAIGHT": "play_straight",
            "PLANE_WITH_ONE": "play_straight",
            "PLANE_WITH_PAIR": "play_straight",
            "FOUR_WITH_TWO": "play_bomb",
            "FOUR_WITH_TWO_PAIRS": "play_bomb",
            "BOMB": "play_bomb",
            "ROCKET": "play_rocket",
        }
    
    def play_bgm(self):
        """播放背景音乐"""
        if not self.bgm_enabled:
            return
        
        # 检查是否有音频文件
        valid_bgm = [f for f in self.bgm_files if os.path.exists(f)]
        
        if valid_bgm:
            # 有音频文件，使用 QMediaPlayer 播放
            bgm_file = random.choice(valid_bgm)
            self.bgm_player.setSource(QUrl.fromLocalFile(os.path.abspath(bgm_file)))
            self.bgm_player.play()
        else:
            # 没有音频文件，启动蜂鸣背景音乐线程
            self._start_beep_bgm()
    
    def _start_beep_bgm(self):
        """启动蜂鸣背景音乐"""
        if self.bgm_loop_running:
            return
        
        self.bgm_loop_running = True
        
        def bgm_loop():
            """背景音乐循环（简单旋律）"""
            # 简单的斗地主背景旋律（欢乐颂变奏）
            notes = [
                (523, 300), (523, 300),  # 5 5
                (587, 300), (659, 300),  # 6 7
                (659, 300), (587, 300),  # 7 6
                (523, 300), (494, 300),  # 5 4
                (440, 300), (440, 300),  # 3 3
                (494, 300), (523, 300),  # 4 5
                (523, 450), (494, 150),  # 5 4
                (494, 600),              # 4
            ]
            
            while self.bgm_loop_running:
                for freq, duration in notes:
                    if not self.bgm_loop_running:
                        break
                    self._play_beep(freq, duration)
                    time.sleep(0.05)
                time.sleep(0.5)  # 每轮之间暂停
        
        self.bgm_thread = threading.Thread(target=bgm_loop, daemon=True)
        self.bgm_thread.start()
    
    def _play_beep(self, frequency, duration):
        """播放蜂鸣音"""
        try:
            # Windows 系统使用 winsound
            import winsound
            winsound.Beep(frequency, duration)
        except (ImportError, AttributeError):
            # Linux/Mac 使用 print 或简单蜂鸣
            print("\a", end="", flush=True)
    
    def stop_bgm(self):
        """停止背景音乐"""
        self.bgm_player.stop()
        self.bgm_loop_running = False
        if self.bgm_thread:
            self.bgm_thread.join(timeout=0.5)
    
    def pause_bgm(self):
        """暂停背景音乐"""
        self.bgm_player.pause()
    
    def resume_bgm(self):
        """恢复背景音乐"""
        if self.bgm_enabled:
            self.bgm_player.play()
    
    def set_bgm_volume(self, volume):
        """设置背景音乐音量 (0.0 - 1.0)"""
        self.bgm_audio.setVolume(volume)
    
    def set_sfx_volume(self, volume):
        """设置音效音量 (0.0 - 1.0)"""
        self.sfx_volume = volume
    
    def toggle_bgm(self, enabled):
        """切换背景音乐开关"""
        self.bgm_enabled = enabled
        if enabled:
            if self.bgm_player.playbackState() != QMediaPlayer.PlayingState:
                self.play_bgm()
        else:
            self.stop_bgm()
    
    def toggle_sfx(self, enabled):
        """切换音效开关"""
        self.sfx_enabled = enabled
    
    def play_sound(self, sound_name):
        """播放指定音效"""
        if not self.sfx_enabled:
            return
        
        sound_file = self.sound_files.get(sound_name)
        if sound_file and os.path.exists(sound_file):
            self._play_audio_file(sound_file)
        else:
            # 使用蜂鸣音效
            self._play_sound_beep(sound_name)
    
    def play_card_sound(self, card_type):
        """根据牌型播放对应音效"""
        sound_name = self.card_type_sounds.get(card_type, "play_card")
        self.play_sound(sound_name)
    
    def _play_audio_file(self, file_path):
        """播放音频文件"""
        player = QMediaPlayer()
        audio_output = QAudioOutput()
        player.setAudioOutput(audio_output)
        audio_output.setVolume(self.sfx_volume)
        
        player.setSource(QUrl.fromLocalFile(os.path.abspath(file_path)))
        player.play()
        
        # 播放完成后清理
        player.mediaStatusChanged.connect(
            lambda status: self._cleanup_player(player, audio_output) 
            if status == QMediaPlayer.EndOfMedia else None
        )
        
        self.sfx_players.append(player)
    
    def _cleanup_player(self, player, audio_output):
        """清理播放完成的播放器"""
        if player in self.sfx_players:
            self.sfx_players.remove(player)
        player.deleteLater()
        audio_output.deleteLater()
    
    def _play_sound_beep(self, sound_name):
        """使用蜂鸣播放音效"""
        # 不同音效使用不同频率和时长
        sound_beeps = {
            "start": (800, 300),
            "win": (1000, 500),
            "lose": (400, 500),
            "landlord": (600, 400),
            "play_card": (500, 100),
            "play_single": (500, 80),
            "play_pair": (600, 80),
            "play_triple": (700, 80),
            "play_straight": (800, 120),
            "play_bomb": (900, 150),
            "play_rocket": (1200, 200),
            "pass": (300, 100),
            "select": (1000, 50),
            "button_click": (700, 50),
            "your_turn": (800, 200),
            "ai_turn": (500, 150),
            "hurry": (1000, 100),
        }
        
        freq, duration = sound_beeps.get(sound_name, (440, 100))
        
        # 在新线程中播放，避免阻塞UI
        def beep_thread():
            try:
                import winsound
                winsound.Beep(freq, duration)
            except (ImportError, AttributeError):
                print("\a", end="", flush=True)
        
        threading.Thread(target=beep_thread, daemon=True).start()
    
    def _on_bgm_status_changed(self, status):
        """背景音乐状态变化处理"""
        if status == QMediaPlayer.EndOfMedia:
            # 检查是否有音频文件
            valid_bgm = [f for f in self.bgm_files if os.path.exists(f)]
            if valid_bgm:
                self.play_bgm()


# 创建全局音效管理器实例
sound_manager = SoundManager()
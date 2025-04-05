# toy_meter
# アプリ概要
	YAESU FTDX10 , FT7100 , FT891 , FT991 をターゲットにした簡易外部メーターとなります。
 	メータはSメーター、SWRメーター、POメーター、ALCメータのみで非常にシンプルです。

# 各種セットアップ
# Raspberry Pi版
	現在、未公開

# macOS版
	macOS 12-15 (Monterey , Ventura , Sonoma , Sequoia)で評価中
	ToyMeter.dmgファイルをダウンロードして、ダブルクリックしてToy_Meterのアプリをインストールしてください。
	Toy_Meterアプリを起動し、リグと通信が確立できない場合、15秒程度で環境設定画面が開きます。
	設定は、この様にテキストディターで開きます。
	———————
 	# 修正後はアプリけーションの再起動を行ってください。
	# After making the correction, restart the application.
 	#
	# SCAN_SPは通信ポート読み出し周期です。0.01〜0.1の間で数字が小さいほど高速周期です。
 	# 	推奨値:FTDX10=0.02 , FT770=xxx , FT891=0.1 , FT991=xxx
	#
	SERIAL_PORT=/dev/cu.usbserial-1410
	BAUD_RATE=38400
	SCAN_SP=0.02
	———————
	SERIAL_PORTは通信ポートの情報です。
	BAUD_RATEは通信速度でリグ側と同じ値にします。
	SCAN_SPはリグから情報取得周期を表します。推奨値は調整中で一番遅い0.1で試してください。
	テキストエディターを閉じて保存します。保存後、アプリケーション終了し、再度立ち上げてください。
	もし、動作中に通信速度、周期を変更したい場合、右下のJP1RXQをクリックしてください。
	設定画面が現れます。設定した場合、必ずアプリは再立ち上げしてください。

# Windows11版
	未開発

# 本アプリ使用中に発生した如何なるトラブルに対して、全て利用者の責任であって、供給者は一切責任は負いません。

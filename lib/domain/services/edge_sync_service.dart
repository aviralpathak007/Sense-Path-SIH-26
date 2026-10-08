import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:latlong2/latlong.dart';
import '../providers/navigation_provider.dart';
import '../../data/models/kinematics.dart';

class EdgeSyncService {
  final NavigationNotifier _notifier;
  WebSocketChannel? _channel;
  bool isConnected = false;

  EdgeSyncService(this._notifier);

  void connect(String url) {
    if (isConnected) return;
    try {
      _channel = WebSocketChannel.connect(Uri.parse(url));
      isConnected = true;
      print("Connected to Edge Engine at \$url");

      _channel?.stream.listen((message) {
        final data = json.decode(message);
        final state = data['state'];

        // Directly inject computed PVA state into the notifier 
        // bypassing the on-device DR engine and sensors
        _notifier.feedEdgeTelemetry(
          LatLng(state['lat'], state['lon']),
          state['bearing'],
          state['speed']
        );
      }, onDone: () {
        print("Edge Engine Disconnected.");
        isConnected = false;
        _reconnect(url);
      }, onError: (e) {
        print("Edge Engine Error: \$e");
        isConnected = false;
        _reconnect(url);
      });
    } catch (e) {
      print("Failed to connect to Edge Engine: \$e");
    }
  }

  void _reconnect(String url) {
    Future.delayed(const Duration(seconds: 2), () {
      if (!isConnected) {
        connect(url);
      }
    });
  }

  void disconnect() {
    _channel?.sink.close();
    isConnected = false;
  }
}

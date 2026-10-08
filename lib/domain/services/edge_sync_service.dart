import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:latlong2/latlong.dart';
import '../providers/navigation_provider.dart';

/// Streams the edge engine's position/velocity/attitude state (external IMU, ~200 Hz propagation).
class EdgeSyncService {
  final NavigationNotifier _notifier;
  WebSocketChannel? _channel;
  bool _wanted = false;

  EdgeSyncService(this._notifier);

  void connect(String url) {
    _wanted = true;
    _open(url);
  }

  void _open(String url) {
    if (!_wanted || _channel != null) return;
    try {
      final channel = WebSocketChannel.connect(Uri.parse(url));
      _channel = channel;
      channel.stream.listen((message) {
        final s = json.decode(message)['state'];
        _notifier.feedEdgeTelemetry(
          pos: LatLng((s['lat'] as num).toDouble(), (s['lon'] as num).toDouble()),
          bearing: (s['bearing'] as num).toDouble(),
          speed: (s['speed'] as num).toDouble(),
          isOutage: s['mode'] == 'dr',
          outageDistance: ((s['outage_distance'] ?? 0) as num).toDouble(),
          driftMeters: (s['drift_m'] as num?)?.toDouble(),
        );
      }, onDone: () => _closed(url), onError: (Object e) {
        debugPrint('Edge engine error: $e');
        _closed(url);
      });
    } catch (e) {
      debugPrint('Failed to connect to edge engine: $e');
      _closed(url);
    }
  }

  void _closed(String url) {
    _channel = null;
    if (_wanted) Future.delayed(const Duration(seconds: 2), () => _open(url));
  }

  void disconnect() {
    _wanted = false;
    _channel?.sink.close();
    _channel = null;
  }
}

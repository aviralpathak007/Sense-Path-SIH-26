import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_map/flutter_map.dart';
import '../../domain/providers/navigation_provider.dart';
import '../../data/models/kinematics.dart';
import '../widgets/custom_puck.dart';
import '../widgets/hud_overlay.dart';
import '../widgets/hackathon_controls.dart';

class NavigationMapScreen extends ConsumerStatefulWidget {
  const NavigationMapScreen({super.key});

  @override
  ConsumerState<NavigationMapScreen> createState() => _NavigationMapScreenState();
}

class _NavigationMapScreenState extends ConsumerState<NavigationMapScreen> {
  final MapController _mapController = MapController();

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(navigationProvider);

    // Keep map centered on user
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _mapController.move(state.position, 16.0);
    });

    return Scaffold(
      body: Stack(
        children: [
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              initialCenter: state.position,
              initialZoom: 16.0,
              interactionOptions: const InteractionOptions(
                flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
              ),
            ),
            children: [
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.example.sense_path',
              ),
              PolylineLayer(
                polylines: [
                  // Historical ground-truth path (Green)
                  if (state.historicalPath.isNotEmpty)
                    Polyline(
                      points: state.historicalPath,
                      strokeWidth: 4.0,
                      color: Colors.green,
                    ),
                  // AI Dead Reckoning trajectory during outages (Orange/Cyan)
                  if (state.drPath.isNotEmpty)
                    Polyline(
                      points: [
                        if (state.historicalPath.isNotEmpty) state.historicalPath.last,
                        ...state.drPath
                      ],
                      strokeWidth: 4.0,
                      color: Colors.orange,
                      pattern: StrokePattern.dashed(segments: const [10.0, 10.0]),
                    ),
                ],
              ),
              MarkerLayer(
                markers: [
                  Marker(
                    point: state.position,
                    width: 60,
                    height: 60,
                    child: CustomPuck(
                      bearing: state.bearing,
                      isBlackout: state.gnssStatus == GnssStatus.blackout,
                    ),
                  ),
                ],
              ),
            ],
          ),
          
          // HUD Overlays
          SafeArea(
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Align(
                    alignment: Alignment.topCenter,
                    child: GnssBadge(status: state.gnssStatus),
                  ),
                ),
                const Spacer(),
                TelemetryHud(
                  speed: state.speed,
                  driftMeters: state.driftMeters,
                  isAligned: state.isAligned,
                ),
              ],
            ),
          ),
        ],
      ),
      floatingActionButton: const HackathonControls(),
      floatingActionButtonLocation: FloatingActionButtonLocation.endTop,
    );
  }
}

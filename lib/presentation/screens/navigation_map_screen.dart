import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:latlong2/latlong.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_map/flutter_map.dart';
import '../../domain/providers/navigation_provider.dart';
import '../../data/models/kinematics.dart';
import '../widgets/custom_puck.dart';
import '../widgets/hud_overlay.dart';
import '../widgets/hackathon_controls.dart';
import '../widgets/fallback_grid_tile_provider.dart';

class NavigationMapScreen extends ConsumerStatefulWidget {
  const NavigationMapScreen({super.key});

  @override
  ConsumerState<NavigationMapScreen> createState() => _NavigationMapScreenState();
}

class _NavigationMapScreenState extends ConsumerState<NavigationMapScreen> {
  final MapController _mapController = MapController();
  List<Polyline> _roads = const []; // bundled OpenStreetMap road network (works offline)

  @override
  void initState() {
    super.initState();
    _loadRoads();
  }

  Future<void> _loadRoads() async {
    final doc = json.decode(await rootBundle.loadString('assets/maps/road_network.json'));
    final lines = <Polyline>[];
    for (final f in doc['features']) {
      final pts = [for (final c in f['geometry']['coordinates']) LatLng((c[1] as num).toDouble(), (c[0] as num).toDouble())];
      lines.add(Polyline(points: pts, strokeWidth: 2.0, color: const Color(0xFF6B7280)));
    }
    if (mounted) setState(() => _roads = lines);
  }

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
                urlTemplate: 'assets/tiles/{z}/{x}/{y}.png',
                tileProvider: FallbackGridTileProvider(),
              ),
              PolylineLayer(polylines: _roads),
              PolylineLayer(
                polylines: [
                  // Reference path (scenario replay only)
                  if (state.truthPath.isNotEmpty)
                    Polyline(points: state.truthPath, strokeWidth: 5.0, color: Colors.greenAccent.withValues(alpha: 0.6)),
                  // Position while GNSS is available (blue)
                  if (state.historicalPath.isNotEmpty)
                    Polyline(
                      points: state.historicalPath,
                      strokeWidth: 3.0,
                      color: Colors.lightBlueAccent,
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
                  outageDistance: state.outageDistance,
                  isAligned: state.isAligned,
                  dataSourceMode: state.dataSourceMode,
                  telemetryHz: state.telemetryHz,
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

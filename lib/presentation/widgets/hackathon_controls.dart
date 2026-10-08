import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../domain/providers/navigation_provider.dart';
import '../../data/models/kinematics.dart';

class HackathonControls extends ConsumerWidget {
  const HackathonControls({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(navigationProvider);
    final notifier = ref.read(navigationProvider.notifier);
    
    final isOutage = state.gnssStatus == GnssStatus.blackout;

    return FloatingActionButton.extended(
      onPressed: () {
        showModalBottomSheet(
          context: context,
          builder: (context) => _buildMenu(context, notifier, isOutage),
        );
      },
      label: const Text('Judge Demo'),
      icon: const Icon(Icons.settings),
      backgroundColor: Colors.deepPurple,
    );
  }

  Widget _buildMenu(BuildContext context, NavigationNotifier notifier, bool isOutage) {
    return Container(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SwitchListTile(
            title: const Text('Simulate GNSS Outage'),
            subtitle: const Text('Cuts off raw GPS, relies on IDR Engine'),
            value: isOutage,
            onChanged: (val) {
              notifier.toggleSimulateOutage(val);
              Navigator.pop(context);
            },
          ),
          ExpansionTile(
            leading: const Icon(Icons.play_circle_fill),
            title: const Text('Load Preset Scenario'),
            subtitle: const Text('Playback real-world IO-VNBD dataset'),
            children: [
              ListTile(
                title: const Text('500m Tunnel Outage'),
                onTap: () {
                  notifier.loadPresetScenario('assets/scenarios/tunnel_blackout_scenario.json');
                  Navigator.pop(context);
                },
              ),
              ListTile(
                title: const Text('Urban Canyon Blackout'),
                onTap: () {
                  notifier.loadPresetScenario('assets/scenarios/tunnel_blackout_scenario.json');
                  Navigator.pop(context);
                },
              ),
              ListTile(
                title: const Text('Stationary Idle (Engine Vibrations)'),
                onTap: () {
                  notifier.loadPresetScenario('assets/scenarios/tunnel_blackout_scenario.json');
                  Navigator.pop(context);
                },
              ),
            ],
          ),
          ListTile(
            leading: const Icon(Icons.align_horizontal_center),
            title: const Text('Calibrate Mount'),
            subtitle: const Text('Re-align phone frame to vehicle'),
            onTap: () {
              notifier.calibrateMount();
              Navigator.pop(context);
            },
          ),
        ],
      ),
    );
  }
}

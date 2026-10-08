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
    
    return FloatingActionButton.extended(
      onPressed: () {
        showModalBottomSheet(
          context: context,
          builder: (context) => _buildMenu(context, notifier, state),
        );
      },
      label: const Text('Judge Demo'),
      icon: const Icon(Icons.settings),
      backgroundColor: Colors.deepPurple,
    );
  }

  Widget _buildMenu(BuildContext context, NavigationNotifier notifier, KinematicsState state) {
    final isOutage = state.gnssStatus == GnssStatus.blackout;
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
            subtitle: const Text('Replays recorded phone IMU; the engine sees live-equivalent input'),
            children: [
              ListTile(
                title: const Text('Held-out drive, 90 s GNSS outage (5x)'),
                subtitle: const Text('IO-VNBD Driver A, never used for training'),
                onTap: () {
                  notifier.loadPresetScenario('assets/scenarios/heldout_outage_scenario.json', speedup: 5);
                  Navigator.pop(context);
                },
              ),
              ListTile(
                title: const Text('Same drive, real time (1x)'),
                onTap: () {
                  notifier.loadPresetScenario('assets/scenarios/heldout_outage_scenario.json', speedup: 1);
                  Navigator.pop(context);
                },
              ),
            ],
          ),
          ListTile(
            title: const Text('Data Source Mode'),
            subtitle: SegmentedButton<DataSourceMode>(
              segments: const [
                ButtonSegment(
                  value: DataSourceMode.internalImu,
                  label: Text('Internal (10Hz)'),
                  icon: Icon(Icons.smartphone),
                ),
                ButtonSegment(
                  value: DataSourceMode.edgeFog,
                  label: Text('Edge engine (200Hz)'),
                  icon: Icon(Icons.router),
                ),
              ],
              selected: {state.dataSourceMode},
              onSelectionChanged: (Set<DataSourceMode> newSelection) {
                notifier.setDataSourceMode(newSelection.first);
                Navigator.pop(context);
              },
            ),
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

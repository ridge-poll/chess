import '../../domain/models/profile.dart';
import '../../domain/repositories.dart';
import '../local/app_database.dart';

class SqliteProfileRepository implements ProfileRepository {
  const SqliteProfileRepository(this.database);
  final AppDatabase database;

  @override
  Future<List<Profile>> list() async {
    final rows = await (await database.instance).query(
      'profiles',
      orderBy: 'created_at ASC',
    );
    return rows.map(Profile.fromMap).toList(growable: false);
  }

  @override
  Future<Profile> create(String name) async {
    final createdAt = DateTime.now().toUtc();
    final connection = await database.instance;
    final id = await connection.insert('profiles', {
      'name': name,
      'created_at': createdAt.toIso8601String(),
    });
    return Profile(id: id, name: name, createdAt: createdAt);
  }
}

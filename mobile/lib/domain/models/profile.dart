class Profile {
  const Profile({
    required this.id,
    required this.name,
    required this.createdAt,
    this.chessComUsername,
    this.syncDays = 7,
  });
  final int id;
  final String name;
  final DateTime createdAt;
  final String? chessComUsername;
  final int syncDays;

  factory Profile.fromMap(Map<String, Object?> map) => Profile(
    id: map['id']! as int,
    name: map['name']! as String,
    createdAt: DateTime.parse(map['created_at']! as String),
    chessComUsername: map['chesscom_username'] as String?,
    syncDays: (map['sync_days'] as int?) ?? 7,
  );
}

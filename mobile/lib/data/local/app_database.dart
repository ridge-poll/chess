import 'package:path/path.dart' as path;
import 'package:sqflite/sqflite.dart';

class AppDatabase {
  AppDatabase({DatabaseFactory? factory, this.databasePath})
    : _factory = factory ?? databaseFactory;

  final DatabaseFactory _factory;
  final String? databasePath;
  Database? _database;

  Future<Database> get instance async => _database ??= await _open();

  Future<Database> _open() async {
    final location =
        databasePath ??
        path.join(await getDatabasesPath(), 'chess_analytics_mobile.sqlite3');
    return _factory.openDatabase(
      location,
      options: OpenDatabaseOptions(
        version: 3,
        onConfigure: (database) => database.execute('PRAGMA foreign_keys = ON'),
        onCreate: (database, version) async {
          await database.execute('''
            CREATE TABLE profiles (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL COLLATE NOCASE UNIQUE,
              created_at TEXT NOT NULL,
              chesscom_username TEXT,
              sync_days INTEGER NOT NULL DEFAULT 7
            )
          ''');
          await database.execute('''
            CREATE TABLE games (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
              fingerprint TEXT NOT NULL,
              played_at TEXT NOT NULL,
              white TEXT NOT NULL,
              black TEXT NOT NULL,
              white_elo INTEGER,
              black_elo INTEGER,
              event TEXT,
              site TEXT,
              eco TEXT,
              time_control TEXT,
              ply_count INTEGER NOT NULL DEFAULT 0,
              player_color TEXT NOT NULL,
              result TEXT NOT NULL,
              opening TEXT,
              time_class TEXT NOT NULL,
              pgn TEXT NOT NULL,
              accuracy REAL,
              estimated_white INTEGER,
              estimated_black INTEGER,
              performance_version TEXT,
              created_at TEXT NOT NULL,
              UNIQUE(profile_id, fingerprint)
            )
          ''');
          await database.execute(
            'CREATE INDEX games_profile_played_at ON games(profile_id, played_at DESC)',
          );
          await database.execute('''
            CREATE TABLE moves (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
              ply INTEGER NOT NULL,
              san TEXT NOT NULL,
              uci TEXT,
              fen_before TEXT,
              fen_after TEXT,
              clock_ms INTEGER,
              UNIQUE(game_id, ply)
            )
          ''');
          await database.execute('''
            CREATE TABLE position_analysis (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
              ply INTEGER,
              fen TEXT NOT NULL,
              depth INTEGER NOT NULL,
              multipv INTEGER NOT NULL DEFAULT 1,
              evaluation_cp INTEGER,
              mate INTEGER,
              best_move_uci TEXT,
              pv_uci TEXT,
              classification TEXT,
              centipawn_loss INTEGER,
              analyzed_at TEXT NOT NULL,
              UNIQUE(fen, depth, multipv)
            )
          ''');
          await database.execute('''
            CREATE TABLE opening_cache (
              position_key TEXT PRIMARY KEY,
              response_json TEXT NOT NULL,
              fetched_at TEXT NOT NULL
            )
          ''');
          await database.execute('''
            CREATE TABLE sync_history (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
              username TEXT NOT NULL,
              started_at TEXT NOT NULL,
              completed_at TEXT,
              imported INTEGER NOT NULL DEFAULT 0,
              duplicates INTEGER NOT NULL DEFAULT 0,
              errors TEXT
            )
          ''');
          await _createAnalysisTables(database);
        },
        onUpgrade: (database, oldVersion, newVersion) async {
          if (oldVersion < 2) {
            await database.execute(
              'ALTER TABLE profiles ADD COLUMN chesscom_username TEXT',
            );
            await database.execute(
              'ALTER TABLE profiles ADD COLUMN sync_days INTEGER NOT NULL DEFAULT 7',
            );
            await database.execute('ALTER TABLE games ADD COLUMN event TEXT');
            await database.execute('ALTER TABLE games ADD COLUMN site TEXT');
            await database.execute('ALTER TABLE games ADD COLUMN eco TEXT');
            await database.execute(
              'ALTER TABLE games ADD COLUMN time_control TEXT',
            );
            await database.execute(
              'ALTER TABLE games ADD COLUMN ply_count INTEGER NOT NULL DEFAULT 0',
            );
            await database.execute('''
              CREATE TABLE sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                username TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                imported INTEGER NOT NULL DEFAULT 0,
                duplicates INTEGER NOT NULL DEFAULT 0,
                errors TEXT
              )
            ''');
          }
          if (oldVersion < 3) {
            await database.execute(
              'ALTER TABLE games ADD COLUMN estimated_white INTEGER',
            );
            await database.execute(
              'ALTER TABLE games ADD COLUMN estimated_black INTEGER',
            );
            await database.execute(
              'ALTER TABLE games ADD COLUMN performance_version TEXT',
            );
            await _createAnalysisTables(database);
          }
        },
      ),
    );
  }

  static Future<void> _createAnalysisTables(Database database) async {
    await database.execute('''
      CREATE TABLE IF NOT EXISTS move_analyses (
        game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
        ply INTEGER NOT NULL,
        depth INTEGER NOT NULL,
        played_uci TEXT NOT NULL,
        best_uci TEXT,
        eval_before_cp INTEGER,
        eval_after_cp INTEGER,
        mate_before INTEGER,
        mate_after INTEGER,
        centipawn_loss INTEGER NOT NULL,
        classification TEXT NOT NULL,
        candidates_json TEXT,
        PRIMARY KEY(game_id, ply, depth)
      )
    ''');
    await database.execute('''
      CREATE TABLE IF NOT EXISTS analysis_jobs (
        game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
        depth INTEGER NOT NULL,
        status TEXT NOT NULL,
        analyzed_plies INTEGER NOT NULL DEFAULT 0,
        total_plies INTEGER NOT NULL,
        error TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY(game_id, depth)
      )
    ''');
    await database.execute('''
      CREATE TABLE IF NOT EXISTS critical_moments (
        game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
        ply INTEGER NOT NULL,
        depth INTEGER NOT NULL,
        polarity TEXT NOT NULL,
        moment_type TEXT NOT NULL,
        score REAL NOT NULL,
        explanation TEXT NOT NULL,
        PRIMARY KEY(game_id, ply, depth)
      )
    ''');
  }

  Future<void> close() async {
    await _database?.close();
    _database = null;
  }
}

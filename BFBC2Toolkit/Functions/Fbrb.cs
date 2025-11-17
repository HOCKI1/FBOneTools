using System;
using System.IO;
using System.Threading.Tasks;
using Microsoft.Win32;
using BFBC2Toolkit.Data;
using BFBC2Toolkit.Helpers;
using BFBC2Shared.Functions;

namespace BFBC2Toolkit.Functions
{
    public class Fbrb
    {
        public static async Task<bool> Extract(string filePath)
        {
            try
            {
                // Закрываем/очищаем MediaStream перед распаковкой
                await MediaStream.Dispose();

                // Определяем путь для распаковки рядом с исходным файлом
                if (string.IsNullOrEmpty(filePath))
                {
                    Log.Write("File path is null or empty!", "error");
                    return true;
                }

                string fileDirectory = Path.GetDirectoryName(filePath);
                string fileNameWithoutExt = Path.GetFileNameWithoutExtension(filePath);
                Dirs.FilesPathData = Path.Combine(fileDirectory, fileNameWithoutExt + " FbRB");

                // Если папка уже существует и это не профиль игры — удаляем её
                if (Directory.Exists(Dirs.FilesPathData) && !Globals.IsGameProfile)
                {
                    await Task.Run(() => Directory.Delete(Dirs.FilesPathData, true));
                }

                // Запускаем Python скрипт для распаковки FBRB
                await Python.ExecuteScript(Dirs.ScriptFbrb, filePath);

                Log.Write("Cleaning up files, please wait...");

                // Теперь FilesPathData точно определён
                if (Directory.Exists(Dirs.FilesPathData))
                {
                    await Task.Run(() => CleanUp.FilesAndDirs(Dirs.FilesPathData));
                }
                else
                {
                    Log.Write($"Extraction folder '{Dirs.FilesPathData}' not found after unpacking!", "warning");
                }

                // Наполняем дерево для UI
                if (Directory.Exists(Dirs.FilesPathData))
                {
                    await Tree.Populate(UIElements.TreeViewDataExplorer, Dirs.FilesPathData);
                }

                Globals.IsDataAvailable = true;
                Globals.IsGameProfile = false;

                return false; // false = успешно
            }
            catch (Exception ex)
            {
                Log.Error(ex.ToString());
                Log.Write("Unable to extract fbrb file! See error.log", "error");
                return true; // true = ошибка
            }
        }


        public static async Task<bool> Archive()
        {
            try
            {
                await MediaStream.Dispose();

                await Python.ExecuteScript(Dirs.ScriptFbrb, Dirs.FilesPathData);

                return false;
            }
            catch (Exception ex)
            {
                Log.Error(ex.ToString());
                Log.Write("Unable to archive fbrb file! See error.log", "error");

                return true;
            }
        }
    }
}

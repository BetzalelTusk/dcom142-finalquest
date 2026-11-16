"""Typed-command questions, Modules 6-8 (paths, textproc, filemgmt, redir, editors).
Sources: the instructor's Module 6, 7 and 8 decks and their in-class exercises."""
from .content_base import R

M6 = "Module 6 slides"
M7 = "Module 7 slides"
M8 = "Module 8 slides"

# ------------------------------------------------------------------ paths (Module 6)
R("paths", "Print the absolute path of the directory you are in", "pwd",
  "pwd = print working directory. At login it shows /home/<username>.",
  M6 + " (Paths and navigation, pwd)", "Three letters.")
R("paths", "Go to your home directory (shortest form, no path given)", "cd;;cd ~",
  "cd with no argument, or cd ~, jumps home. ~ is the shortcut for your home directory.",
  M6 + " (cd shortcuts)", "No argument needed.")
R("paths", "Move up one level to the parent directory", "cd ..",
  ".. is the parent directory and . is the current one. cd . would stay where you are.",
  M6 + " (cd shortcuts)", "Two dots.")
R("paths", "Change to /etc/ssl using an ABSOLUTE path", "cd /etc/ssl",
  "An absolute path starts at / and works from anywhere. A relative path like cd ssl only works from /etc.",
  M6 + " (absolute vs relative paths)", "Start from the root.")
R("paths", "Change to the directory dir1 that sits inside your current directory (relative path)", "cd dir1",
  "No leading / means relative: it starts from where you are now.",
  M6 + " (relative paths)")
R("paths", "List the current directory in long format AND show each file's inode number", "ls -li",
  "-l is long format and -i adds the inode number. Hard links share an inode; symbolic links get their own.",
  M6 + " (ls -li, links)", "Two flags, one group.")
R("paths", "Create an empty file named file1", "touch file1",
  "touch creates an empty file (or updates the time of an existing one).",
  M6 + " (Creating files and directories)")
R("paths", "Create two directories, dir1 and dir2, with a single command", "mkdir dir1 dir2",
  "mkdir accepts several names at once.", M6 + " (mkdir)")
R("paths", "Show file1's metadata: size, inode, links, permissions, and Access/Modify/Change/Birth times", "stat file1",
  "stat prints the full inode metadata, including all the timestamps. ls -l shows far less.",
  M6 + " (stat)")
R("paths", "Create a HARD link named file2-hl that points to file2", "ln file2 file2-hl",
  "No -s means hard link: same inode, link count goes to 2, data survives if file2 is deleted. Order is ln <existing> <new>.",
  M6 + " (Links, ln)", "No flags.")
R("paths", "Create a SYMBOLIC (soft) link named file3-sl that points to file3", "ln -s file3 file3-sl",
  "-s makes a symbolic link with its own inode (type l, shown file3-sl -> file3). It breaks if file3 is deleted.",
  M6 + " (Links, ln -s)", "One flag.")
R("paths", 'Find regular FILES (not directories) in the current directory whose name starts with file1',
  'find -type f -name "file1*";;find . -type f -name "file1*";;find -name "file1*" -type f;;find . -name "file1*" -type f',
  "-type f restricts to files and -name takes a pattern; quote the * so the shell does not expand it first.",
  M6 + " (find)", "-type and -name.")
R("paths", "Find DIRECTORIES named dir1 starting from the current directory",
  "find -type d -name dir1;;find . -type d -name dir1;;find -name dir1 -type d;;find . -name dir1 -type d",
  "-type d limits the search to directories. -type f would be files only.",
  M6 + " (find -type d)")
R("paths", "As root-level search, find every file named passwd under /etc", "find /etc -name passwd",
  "find {where} {option} {criteria}: the starting directory comes first, then -name.",
  M6 + " (find examples)", "Where first, then the criteria.")
R("paths", "Which top-level directory holds system configuration files? (type the path)", "/etc;;etc",
  "/etc holds config files. /var/log holds logs, /home holds user directories, /opt optional software.",
  M6 + " (Key directories, FHS)", "Starts with e.", loose=True)
R("paths", "Which directory holds log files? (type the full path)", "/var/log;;var/log",
  "/var holds variable data and /var/log is where logs such as /var/log/messages and /var/log/secure live.",
  M6 + " (Key directories, FHS)", loose=True)

# ------------------------------------------------------------------ textproc (Module 6)
R("textproc", 'Convert the text "hello world" to uppercase by piping echo into tr',
  'echo "hello world" | tr "a-z" "A-Z"',
  "tr translates characters one-for-one: a-z becomes A-Z. The output is HELLO WORLD.",
  M6 + " (tr)", "echo, a pipe, then tr with two ranges.")
R("textproc", "Count only the LINES in file1", "wc -l file1",
  "wc with no flag prints lines, words and bytes. -l is lines, -w words, -c bytes.",
  M6 + " (wc)")
R("textproc", "Count only the WORDS in file1", "wc -w file1",
  "-w words. -c would be bytes and -l would be lines.", M6 + " (wc)")
R("textproc", "Count only the BYTES (characters) in file1", "wc -c file1",
  "-c counts bytes. The slide notes it as bytes/characters.", M6 + " (wc)")
R("textproc", "Sort file1 numerically, largest first", "sort -nr file1",
  "-n compares as numbers and -r reverses to descending. Without -n, 10 sorts before 9 as text.",
  M6 + " (sort)", "Two flags: numeric and reverse.")
R("textproc", "Sort file1 on its 2nd field, where fields are separated by a colon",
  "sort -t: -k2 file1;;sort -k2 -t: file1;;sort -t : -k 2 file1;;sort -k 2 -t : file1",
  "-t sets the field separator and -k picks the field number.",
  M6 + " (sort -k, -t)")
R("textproc", "List just the usernames (1st colon-separated field) from /etc/passwd, showing only the first 10 lines",
  "cut -d: -f1 /etc/passwd | head;;cut -d : -f 1 /etc/passwd | head",
  "cut -d: sets the delimiter and -f1 keeps field 1, then head trims to 10 lines.",
  M6 + " (cut, head)", "cut, then a pipe to head.")
R("textproc", "Show only the first 3 characters of every line of file1", "cut -c1-3 file1;;cut -c 1-3 file1",
  "-c cuts by character position. -f would cut by field instead.", M6 + " (cut -c)")
R("textproc", "Show the first 10 lines of /etc/passwd (the default amount)", "head /etc/passwd;;head -n 10 /etc/passwd;;head -n10 /etc/passwd",
  "head defaults to 10 lines. -n changes how many.", M6 + " (head)")
R("textproc", "Compare file1 and file2 side by side", "sdiff file1 file2",
  "sdiff shows the files in two columns: | = lines differ, < = line only in the left file.",
  M6 + " (sdiff)")
R("textproc", 'Use awk to print the lines of file1 that match "Linux"', 'awk /Linux/ file1;;awk "/Linux/" file1',
  "awk works by pattern or by field. A /pattern/ with no action prints matching lines.",
  M6 + " (awk)", "awk, a slash pattern, the file.")
R("textproc", "Use sed to replace every occurrence of old with new in file1 (print the result)", "sed s/old/new/g file1",
  "s substitutes and the g flag makes it global (every occurrence per line). Without g only the first match changes. The slide lists the idea but has no example.",
  M6 + " (sed, no example on slide)", "s///g")
R("textproc", "Use sed to delete the lines of file1 that contain Linux", "sed /Linux/d file1",
  "The d command deletes lines that match the pattern.", M6 + " (sed d)")
R("textproc", "Use sed to print ONLY the lines of file1 containing Linux", "sed -n /Linux/p file1",
  "-n suppresses normal output and p prints just the matches, so you get a grep-like result.",
  M6 + " (sed -n with p)", "-n and p together.")

# ------------------------------------------------------------------ filemgmt (Module 7)
R("filemgmt", "Show the current username", "whoami", "whoami prints the account you are logged in as.",
  M7 + " (Review / navigation)")
R("filemgmt", "Show the system's hostname", "hostname", "hostname prints the name of the machine.",
  M7 + " (Review / navigation)")
R("filemgmt", "Display the directories and files below here as a hierarchy", "tree",
  "tree draws the directory structure as a tree.", M7 + " (tree)")
R("filemgmt", "Open the manual page for ls", "man ls", "man <command> opens its manual page.", M7 + " (man)")
R("filemgmt", "List ALL files, including hidden ones, in long format", "ls -la",
  "-a shows hidden dotfiles and -l is long format.", M7 + " (ls options)")
R("filemgmt", "List the current directory in long format with human-readable sizes", "ls -lh",
  "-h turns byte counts into K, M, G. It needs -l to show sizes at all.", M7 + " (ls options)")
R("filemgmt", "List files sorted by SIZE (short form, no long format)", "ls -S",
  "-S sorts by size (largest first). -t sorts by modification time instead.", M7 + " (ls options)")
R("filemgmt", "List files sorted by modification TIME (short form, no long format)", "ls -t",
  "-t sorts by modification time, newest first.", M7 + " (ls options)")
R("filemgmt", "List the contents of this directory AND every directory below it", "ls -R",
  "-R is recursive.", M7 + " (ls options)")
R("filemgmt", "Show the directory dir1 itself in the listing, not what is inside it (no long format)", "ls -d dir1",
  "-d lists the directory entry itself, which is how you check a directory's own permissions with -ld.",
  M7 + " (ls -d)")
R("filemgmt", "Copy /etc/hosts into your current directory", "cp /etc/hosts .",
  "cp {source} {destination}; . means here. The original stays where it is.", M7 + " (cp)", "Destination is a single dot.")
R("filemgmt", "Copy the directory dir1 to dir9, including everything inside", "cp -R dir1 dir9;;cp -r dir1 dir9",
  "cp needs -R to copy a directory. Without it you get 'omitting directory'.", M7 + " (cp -R)")
R("filemgmt", "Rename the file hosts to new-hosts", "mv hosts new-hosts",
  "mv renames when the target is a new name in the same place. Unlike cp, the original does not stay.", M7 + " (mv)")
R("filemgmt", "Move the file moduli into the directory dir1", "mv moduli dir1",
  "mv moves when the target is an existing directory.", M7 + " (mv)")
R("filemgmt", "Show the last 10 lines of /etc/passwd (the default amount)", "tail /etc/passwd;;tail -n 10 /etc/passwd;;tail -n10 /etc/passwd",
  "tail defaults to 10 lines and is great for the newest entries in a log.", M7 + " (head / tail)")
R("filemgmt", "Show only the first 5 lines of /etc/passwd", "head -n 5 /etc/passwd;;head -n5 /etc/passwd;;head -5 /etc/passwd",
  "-n sets the number of lines.", M7 + " (head -n)")
R("filemgmt", "Page through /etc/passwd with the preferred pager (the one with more features)", "less /etc/passwd",
  "less beats more because it can scroll backwards and search. more /etc/passwd also pages.", M7 + " (less / more)")
R("filemgmt", "Print the whole of file1 to the screen", "cat file1", "cat prints an entire file; fine for small ones.",
  M7 + " (cat)")
R("filemgmt", "Delete the EMPTY directory dir3", "rmdir dir3;;rm -d dir3",
  "rmdir only removes empty directories. For a full one you need rm -R.", M7 + " (rmdir)")
R("filemgmt", "Force-delete the directory dir1 and everything inside it, no prompts", "rm -fR dir1;;rm -rf dir1",
  "-f is force and -R is recursive. There is no trash: it is gone for good. The slide uses capital -R.",
  M7 + " (rm)", "Two flags: force and recursive.")
R("filemgmt", "Delete file1, asking for confirmation first", "rm -i file1",
  "-i is interactive: it asks before each delete. -f would never ask.", M7 + " (rm -i)")
R("filemgmt", "Delete every file in the current directory whose name starts with file", "rm file*",
  "The * wildcard expands to all matching names before rm runs.", M7 + " (rm with wildcard)")

# ------------------------------------------------------------------ redir (Module 7)
R("redir", "Show the lines of /etc/passwd containing Rocky, ignoring upper/lower case", "grep -i Rocky /etc/passwd",
  "-i ignores case, so Rocky also matches rocky.", M7 + " (grep -i)")
R("redir", "Count the lines of /etc/passwd that contain root", "grep -c root /etc/passwd",
  "-c prints the number of matching LINES, not the matches themselves.", M7 + " (grep -c)")
R("redir", 'Search /var/log/messages for "error", case-insensitive, and print only the COUNT of matching lines (need root)',
  'sudo grep -ic "error" /var/log/messages;;grep -ic "error" /var/log/messages',
  "Without sudo you get 'Permission denied' on that log. -i and -c combine as -ic.", M7 + " (grep -ic, logs)")
R("redir", 'Show the lines containing "Failed password" in /var/log/secure, ignoring case (use sudo)',
  'sudo grep -i "Failed password" /var/log/secure;;grep -i "Failed password" /var/log/secure',
  "The security-analyst scenario: failed SSH logins are recorded in /var/log/secure. Quote the two-word pattern.",
  M7 + " (grep, security scenario)")
R("redir", 'Count the "Failed password" lines in /var/log/secure, ignoring case (use sudo)',
  'sudo grep -ic "Failed password" /var/log/secure;;grep -ic "Failed password" /var/log/secure',
  "-ic = ignore case + count. Handy to see how many failed logins there were.", M7 + " (grep -ic)")
R("redir", "Show every line in /var/log/secure that mentions the address 192.168.1.103, ignoring case (use sudo)",
  "sudo grep -i 192.168.1.103 /var/log/secure;;grep -i 192.168.1.103 /var/log/secure",
  "Search for the attacker's IP in the log; grep prints each matching line.", M7 + " (grep, security scenario)")
R("redir", "Send the output of echo Hello to file1, OVERWRITING it", "echo Hello > file1;;echo Hello >file1",
  "> sends stdout to a file and replaces what was there. >> would append.", M7 + " (Redirection)")
R("redir", "Add the text bye to the END of file1 without erasing it", "echo bye >> file1;;echo bye >>file1",
  ">> appends stdout to the file.", M7 + " (Redirection)")
R("redir", "Run cd file1 and send its ERROR output to a file named error, overwriting", "cd file1 2> error;;cd file1 2>error",
  "2> redirects stderr (stream 2). Plain > only catches stdout, so the error would still show on screen.",
  M7 + " (Redirection, 2>)")
R("redir", "Run cd file1 and APPEND its error output to a file named error", "cd file1 2>> error;;cd file1 2>>error",
  "2>> appends stderr. This is the exact example on the slide.", M7 + " (Redirection, 2>>)")
R("redir", "Run ls /nonexistent and send BOTH stdout and stderr to a file named out.txt", "ls /nonexistent &> out.txt;;ls /nonexistent &>out.txt",
  "&> captures both streams in one file.", M7 + " (Redirection, &>)")
R("redir", 'Feed /etc/hosts INTO tr as input (use input redirection, not a pipe) to uppercase it',
  'tr "a-z" "A-Z" < /etc/hosts;;tr "a-z" "A-Z" </etc/hosts',
  "< reads stdin from a file. This is the slide's example.", M7 + " (Redirection, <)")
R("redir", "Run cat with a here document that stops at a line containing END", "cat <<END;;cat << END",
  "<<string is a here document: input continues until a line containing that string.", M7 + " (Redirection, <<)")
R("redir", "Show whoami's output on screen AND save it to file2 at the same time", "whoami | tee file2",
  "tee writes to the screen and to the file. > alone would only write to the file.", M7 + " (tee)")
R("redir", "Delete every file matching file*.* by feeding the ls output to rm with xargs", "ls file*.* | xargs rm",
  "xargs turns stdin into arguments for rm. The slide's typo 'xarg' fails with 'command not found'.", M7 + " (xargs)")
R("redir", "Make dir1 and then cd into it, but only if mkdir succeeded", "mkdir dir1 && cd dir1",
  "&& runs the next command only if the previous one succeeded.", M7 + " (Chaining, &&)")
R("redir", "Run cd dir9 and, only if that FAILS, run echo failed", "cd dir9 || echo failed",
  "|| runs the next command only if the previous one failed.", M7 + " (Chaining, ||)")
R("redir", "Run pwd and then whoami, no matter whether the first one worked", "pwd; whoami;;pwd ; whoami;;pwd;whoami",
  "; runs commands in sequence regardless of the result.", M7 + " (Chaining, ;)")
R("redir", "Use a pipe to show only the lines of /etc/passwd that contain bash, starting from cat", "cat /etc/passwd | grep bash",
  "| sends the output of one command to the input of the next.", M7 + " (Pipes)")
R("redir", "Which two-character operator means AND (run the next command only on success)?", "&&",
  "&& = AND, || = OR. ; always continues.", M7 + " (Chaining)")
R("redir", "Which two-character operator APPENDS stdout to a file?", ">>",
  ">> appends; > overwrites; 2>> appends stderr.", M7 + " (Redirection)")

# ------------------------------------------------------------------ editors (Module 8)
R("editors", "Open the file file1 in vim", "vim file1", "vim <file> opens it in the Vim editor.", M8 + " (vim)")
R("editors", "Which key returns Vim to COMMAND mode (its default mode)?", "Esc;;ESC;;Escape",
  "ESC = Command mode. i or a etc = Insert mode. : = Execute mode.", M8 + " (vim modes)", "Top-left key.", loose=True)
R("editors", "Which key starts Execute mode in Vim?", ":",
  ": opens the command line for :w, :q, :wq, :q!", M8 + " (vim modes)")
R("editors", "In Vim command mode: insert at the START of the current line", "I",
  "Capital I = start of line. Lowercase i inserts before the cursor.", M8 + " (vim insert keys)", "Capital letter.")
R("editors", "In Vim command mode: insert AFTER the cursor", "a",
  "a = after the cursor, A = end of line.", M8 + " (vim insert keys)")
R("editors", "In Vim command mode: insert at the END of the current line", "A",
  "Capital A = end of line.", M8 + " (vim insert keys)", "Capital letter.")
R("editors", "In Vim command mode: open a new line BELOW the cursor and start inserting", "o",
  "o = new line below, O = new line above.", M8 + " (vim insert keys)")
R("editors", "Vim execute mode: save the file and quit", ":wq",
  ":w saves, :q quits, :wq does both.", M8 + " (vim execute commands)")
R("editors", "Vim execute mode: quit WITHOUT saving", ":q!",
  "The ! forces the quit and discards changes. Plain :q refuses if there are unsaved changes.", M8 + " (vim execute commands)")
R("editors", "Vim execute mode: save the file under the new name notes2", ":w notes2",
  ":w newfilename saves a copy under that name.", M8 + " (vim execute commands)")
R("editors", "Vim command mode: jump to line 42", "42G", "<number>G goes to that line. G alone goes to the bottom.", M8 + " (vim navigation)")
R("editors", "Vim command mode: go to the TOP of the file", "gg", "gg = top, G = bottom.", M8 + " (vim navigation)")
R("editors", "Vim command mode: delete the current line", "dd", "dd deletes the line. d deletes the word at the cursor (per the slide).", M8 + " (vim delete)")
R("editors", "Vim: split the window horizontally (the key chord after Ctrl+W)", "Ctrl+W s;;Ctrl+W then s",
  "Ctrl+W then s splits horizontally and v splits vertically.", M8 + " (vim split windows)", loose=True)
R("editors", "nano: which keystroke SAVES the file (write out / save as)?", "Ctrl+O;;Ctrl+S",
  "The slide lists Ctrl+S as save and Ctrl+O as write out (save as). Either is accepted here.", M8 + " (nano)", loose=True)
R("editors", "nano: which keystroke EXITS the editor?", "Ctrl+X", "Ctrl+X exits nano; it asks to save first if there are changes.", M8 + " (nano)", loose=True)
R("editors", "nano: which keystroke jumps to the START of the current line?", "Ctrl+A", "Ctrl+A = start of line, Ctrl+E = end of line.", M8 + " (nano)", loose=True)
R("editors", "nano: which keystroke jumps to the END of the current line?", "Ctrl+E", "Ctrl+E = end, Ctrl+A = start.", M8 + " (nano)", loose=True)
R("editors", "Launch the GNOME graphical text editor from the command line", "gedit",
  "gedit is the GNOME GUI editor and can be started from the CLI.", M8 + " (gedit)")

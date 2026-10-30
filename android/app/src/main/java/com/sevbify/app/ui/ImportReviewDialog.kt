package com.sevbify.app.ui

import com.sevbify.app.tr
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.sevbify.app.ImportCheck
import com.sevbify.app.Playlist

/** "Check the spelling": the imported songs that couldn't be found, each with the closest song filled in. */
@Composable
fun ImportReviewDialog(pl: Playlist, problems: List<ImportCheck.Problem>) {
    val texts = remember(problems) { mutableStateListOf(*problems.map { it.suggestion.ifEmpty { it.written } }.toTypedArray()) }
    val ticked = remember(problems) { mutableStateListOf(*problems.map { it.suggestion.isNotEmpty() }.toTypedArray()) }
    AlertDialog(
        onDismissRequest = { ImportCheck.review = null },
        title = { Text(tr("Check the spelling")) },
        text = {
            Column {
                Text("${problems.size} song${if (problems.size == 1) "" else "s"} in “${pl.name}” couldn't be found as " +
                     "written, so they can't stream or download yet. Sevbify filled in the closest song it found. Or " +
                     "fix those lines in your file and import it again.", style = MaterialTheme.typography.bodySmall)
                LazyColumn(Modifier.heightIn(max = 420.dp).padding(top = 8.dp)) {
                    itemsIndexed(problems) { i, p ->
                        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 4.dp)) {
                            Checkbox(ticked[i], { ticked[i] = it }, colors = CheckboxDefaults.colors(checkedColor = C.Green))
                            Column(Modifier.weight(1f)) {
                                Text("#${p.index + 1}  ${p.written}", style = MaterialTheme.typography.bodySmall, color = C.Sub)
                                OutlinedTextField(texts[i], { texts[i] = it; ticked[i] = true }, singleLine = true,
                                                  modifier = Modifier.fillMaxWidth())
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = {
                val fixes = problems.indices.filter { ticked[it] && texts[it].isNotBlank() && texts[it] != problems[it].written }
                    .associate { problems[it].index to texts[it].trim() }
                ImportCheck.apply(pl, fixes)
            }) { Text(tr("Fix the ticked songs"), color = C.Green) }
        },
        dismissButton = { TextButton(onClick = { ImportCheck.review = null }) { Text(tr("Keep as written"), color = C.Text) } },
        containerColor = C.Elevated,
    )
}
